"""SQLAdmin 管理后台和 ChatBI RBAC（基于角色的访问控制）边界。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from sqlalchemy import event, func, inspect, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import Response
from wtforms import PasswordField
from wtforms.validators import Optional

from src.authorization.auth_service import (
    AuthenticationFailed,
    AuthService,
    SessionExpired,
)
from src.authorization.audit_service import AuditRecord, AuditUnavailable
from src.authorization.contracts import AuthContext
from src.authorization.passwords import hash_password

from .bootstrap import FIXED_ROLES, normalize_username
from .models import AuditEvent, Permission, Role, User, UserSession

FIXED_ROLE_NAMES = frozenset(name for name, _ in FIXED_ROLES)
ADMIN_PERMISSION_NAMES = frozenset({"admin.users", "admin.roles", "admin.audit"})
_ADMIN_AUDIT_RECORDS = "_chatbi_admin_audit_records"
_ADMIN_AUDIT_SINK = "_chatbi_admin_audit_sink"


class AdminPolicyError(RuntimeError):
    """管理操作违反 ChatBI 的固定 RBAC Contract。"""


class LastAdminError(AdminPolicyError):
    """操作会让系统失去最后一个可管理管理员。"""


def is_admin_context(auth_context: AuthContext) -> bool:
    """V1 管理后台需要至少一个管理员管理权限。"""

    return bool(auth_context.permissions & ADMIN_PERMISSION_NAMES)


def validate_user_mutation(
    session: Session,
    *,
    user_id: int,
    is_active: bool,
    roles: list[Role] | tuple[Role, ...],
) -> None:
    """在同一 SQLAlchemy transaction（事务）内保护最后一个 active admin。"""

    role_names = {role.name for role in roles}
    if not role_names.issubset(FIXED_ROLE_NAMES):
        raise AdminPolicyError("只能分配代码固定的 admin 或 analyst 角色")
    if is_active and "admin" in role_names:
        return

    remaining_admins = session.scalar(
        select(func.count(User.id))
        .join(User.roles)
        .where(
            User.is_active.is_(True),
            Role.name == "admin",
            User.id != user_id,
        )
    )
    if not remaining_admins:
        raise LastAdminError("不能移除最后一个 active admin")


def set_user_roles(
    session_factory: Any,
    *,
    user_id: int,
    role_names: set[str] | frozenset[str],
) -> None:
    """供管理入口和确定性测试复用的用户角色变更 Service。"""

    if not role_names.issubset(FIXED_ROLE_NAMES):
        raise AdminPolicyError("只能分配代码固定的 admin 或 analyst 角色")
    with session_factory() as session, session.begin():
        user = session.get(User, user_id)
        if user is None:
            raise AdminPolicyError("用户不存在")
        roles = list(
            session.scalars(select(Role).where(Role.name.in_(role_names))).all()
        )
        validate_user_mutation(
            session,
            user_id=user.id,
            is_active=user.is_active,
            roles=roles,
        )
        user.roles = roles


class ChatBIAdminAuthenticationBackend(AuthenticationBackend):
    """让 SQLAdmin 的签名 Cookie 只保存 ChatBI 数据库 Session Token。"""

    def __init__(self, auth_service: AuthService, *, secret_key: str) -> None:
        super().__init__(secret_key)
        self._auth_service = auth_service

    async def login(self, request: Request) -> Response | bool:
        form = await request.form()
        username = form.get("username", "")
        password = form.get("password", "")
        try:
            result = self._auth_service.login(str(username), str(password))
        except AuthenticationFailed:
            return False
        if result.auth_context.must_change_password:
            return Response(
                "请先通过 /auth/login 和 /auth/change-password 完成首次改密。",
                status_code=403,
                media_type="text/plain",
            )
        if not is_admin_context(result.auth_context):
            return Response("当前用户没有管理后台权限。", status_code=403)
        request.session["chatbi_session_token"] = result.token
        return True

    async def authenticate(self, request: Request) -> Response | bool:
        raw_token = request.session.get("chatbi_session_token")
        if not isinstance(raw_token, str) or not raw_token:
            return False
        try:
            context = self._auth_service.authenticate_session(raw_token)
        except SessionExpired:
            request.session.clear()
            return False
        if context.must_change_password:
            return Response("请先完成首次改密。", status_code=403)
        if not is_admin_context(context):
            return Response("当前用户没有管理后台权限。", status_code=403)
        request.state.chatbi_auth_context = context
        return True

    async def logout(self, request: Request) -> Response | bool:
        raw_token = request.session.get("chatbi_session_token")
        if isinstance(raw_token, str) and raw_token:
            try:
                self._auth_service.logout(raw_token)
            except SessionExpired:
                pass
        request.session.clear()
        return True


class UserAdmin(ModelView, model=User):
    """用户管理：隐藏密码和内部锁定字段，禁止物理删除。"""

    name = "用户"
    name_plural = "用户"
    icon = "fa-solid fa-users"
    can_delete = False
    column_list = [User.id, User.username, User.is_active, User.must_change_password]
    column_details_exclude_list = [
        User.password_hash,
        User.failed_login_count,
        User.locked_until,
    ]
    form_columns = [
        User.username,
        User.password_hash,
        User.is_active,
        User.must_change_password,
        User.roles,
    ]
    form_overrides = {"password_hash": PasswordField}
    form_args = {"password_hash": {"validators": [Optional()]}}
    form_widget_args = {"password_hash": {"autocomplete": "new-password"}}
    column_labels = {
        User.username: "用户名",
        User.password_hash: "初始密码 / 重置密码",
        User.is_active: "启用",
        User.must_change_password: "首次登录改密",
        User.roles: "角色",
    }

    async def on_model_change(
        self,
        data: dict[str, Any],
        model: User,
        is_created: bool,
        request: Request,
    ) -> None:
        if "username" in data:
            data["username"] = normalize_username(data["username"])

        raw_password = data.get("password_hash")
        if raw_password:
            data["password_hash"] = hash_password(raw_password)
            data["must_change_password"] = True
        elif is_created:
            raise AdminPolicyError("创建用户必须设置至少 12 位初始密码")
        else:
            data.pop("password_hash", None)

        if not is_created:
            session = inspect(model).session
            if session is None:
                raise AdminPolicyError("无法确认用户变更事务")
            roles = _resolve_roles(
                session,
                data.get("roles"),
                current_roles=model.roles,
            )
            validate_user_mutation(
                session,
                user_id=model.id,
                is_active=data.get("is_active", model.is_active),
                roles=roles,
            )
            if data.get("is_active", model.is_active) is False:
                _revoke_sessions(session, model.id)
            if raw_password:
                _revoke_sessions(session, model.id)

            pending_events: list[AuditRecord] = []
            actor_user_id = _actor_user_id(request)
            if data.get("is_active", model.is_active) != model.is_active:
                pending_events.append(
                    AuditRecord(
                        event_type=(
                            "user.enable"
                            if data.get("is_active", model.is_active)
                            else "user.disable"
                        ),
                        target_type="user",
                        target_id=str(model.id),
                        outcome="success",
                        actor_user_id=actor_user_id,
                        reason=(
                            "USER_ENABLED"
                            if data.get("is_active", model.is_active)
                            else "USER_DISABLED"
                        ),
                    )
                )
            if raw_password:
                pending_events.append(
                    AuditRecord(
                        event_type="auth.password_reset",
                        target_type="user",
                        target_id=str(model.id),
                        outcome="success",
                        actor_user_id=actor_user_id,
                        reason="PASSWORD_RESET",
                    )
                )
            if "roles" in data and _role_names(roles) != _role_names(model.roles):
                pending_events.append(
                    AuditRecord(
                        event_type="user.roles_update",
                        target_type="user",
                        target_id=str(model.id),
                        outcome="success",
                        actor_user_id=actor_user_id,
                        reason="ROLES_UPDATED",
                    )
                )
            _mark_admin_audit(model, request, pending_events)

        elif is_created:
            _mark_admin_audit(
                model,
                request,
                [
                    AuditRecord(
                        event_type="user.create",
                        target_type="user",
                        target_id=str(data.get("username") or model.username),
                        outcome="success",
                        actor_user_id=_actor_user_id(request),
                        request_id=_request_id(request),
                        reason="USER_CREATED",
                    )
                ],
            )


class RoleAdmin(ModelView, model=Role):
    """V1 角色目录只读，避免后台自由制造权限语义。"""

    name = "角色"
    name_plural = "角色"
    icon = "fa-solid fa-user-shield"
    can_create = False
    can_edit = False
    can_delete = False
    column_list = [Role.id, Role.name, Role.description]
    form_columns = [Role.name, Role.description]


class PermissionAdmin(ModelView, model=Permission):
    """V1 权限目录由代码固定，只读展示。"""

    name = "权限"
    name_plural = "权限"
    icon = "fa-solid fa-key"
    can_create = False
    can_edit = False
    can_delete = False
    column_list = [Permission.id, Permission.name, Permission.description]
    form_columns = [Permission.name, Permission.description]


class AuditEventAdmin(ModelView, model=AuditEvent):
    """审计事件只读展示，避免后台修改或删除安全记录。"""

    name = "审计事件"
    name_plural = "审计事件"
    icon = "fa-solid fa-clipboard-list"
    can_create = False
    can_edit = False
    can_delete = False
    column_list = [
        AuditEvent.id,
        AuditEvent.event_type,
        AuditEvent.target_type,
        AuditEvent.target_id,
        AuditEvent.outcome,
        AuditEvent.request_id,
        AuditEvent.reason,
        AuditEvent.created_at,
    ]
    form_columns = column_list


def mount_admin(
    app: FastAPI,
    *,
    engine: Engine,
    auth_service: AuthService,
    secret_key: str,
    session_factory: Any | None = None,
    audit_sink: object | None = None,
) -> Admin:
    """把 SQLAdmin 挂载到 FastAPI，并确保它只使用应用库 Engine。"""

    maker = session_factory or sessionmaker(engine, expire_on_commit=False)
    backend = ChatBIAdminAuthenticationBackend(auth_service, secret_key=secret_key)
    admin = Admin(
        app,
        engine=engine,
        session_maker=maker,
        base_url="/admin",
        title="ChatBI 管理后台",
        authentication_backend=backend,
    )
    admin.add_view(UserAdmin)
    admin.add_view(RoleAdmin)
    admin.add_view(PermissionAdmin)
    admin.add_view(AuditEventAdmin)
    app.state.sqladmin = admin
    app.state.sqladmin_engine = engine
    app.state.audit_sink = audit_sink
    # SQLAdmin 请求落在它自己的 Starlette 子应用上，不会自动继承 FastAPI
    # 根应用的 State；审计 Sink 必须显式放到这个请求边界上。
    admin.admin.state.audit_sink = audit_sink
    return admin


def _revoke_sessions(session: Session, user_id: int) -> None:
    session.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


def _actor_user_id(request: Request) -> int | None:
    context = getattr(request.state, "chatbi_auth_context", None)
    return context.user_id if isinstance(context, AuthContext) else None


def _request_id(request: Request) -> str:
    value = request.headers.get("X-Request-ID")
    return value.strip() if isinstance(value, str) and value.strip() else "sqladmin"


def _role_names(roles: Any) -> frozenset[str]:
    return frozenset(role.name for role in roles if hasattr(role, "name"))


def _resolve_roles(
    session: Session,
    raw_roles: Any,
    *,
    current_roles: list[Role],
) -> list[Role]:
    """把 SQLAdmin 表单中的角色 ID 转换为已认证的 Role 对象。"""

    if raw_roles is None:
        return list(current_roles)
    values = [raw_roles] if isinstance(raw_roles, (str, int)) else list(raw_roles)
    if not values:
        return []
    if all(isinstance(value, Role) for value in values):
        return values
    try:
        role_ids = [int(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise AdminPolicyError("角色表单值无效") from exc
    roles = list(session.scalars(select(Role).where(Role.id.in_(role_ids))).all())
    if len(roles) != len(set(role_ids)):
        raise AdminPolicyError("只能分配代码固定的 admin 或 analyst 角色")
    return roles


def _write_admin_audit(
    sink: object,
    session: Session,
    record: AuditRecord,
) -> None:
    writer = getattr(sink, "write", None)
    if not callable(writer):
        raise AuditUnavailable("ChatBI 审计 Sink 不支持事务内写入")
    try:
        writer(session, record)
    except AuditUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 - management audit must Fail Closed
        raise AuditUnavailable("ChatBI 审计写入失败") from exc


def _mark_admin_audit(
    model: User,
    request: Request,
    records: list[AuditRecord],
) -> None:
    sink = getattr(request.app.state, "audit_sink", None)
    if sink is None or not records:
        return
    setattr(model, _ADMIN_AUDIT_RECORDS, records)
    setattr(model, _ADMIN_AUDIT_SINK, sink)


@event.listens_for(Session, "before_flush")
def _write_marked_admin_audit(
    session: Session,
    flush_context: object,
    instances: object,
) -> None:
    del flush_context, instances
    for model in [*session.new, *session.dirty]:
        records = getattr(model, _ADMIN_AUDIT_RECORDS, None)
        if not isinstance(model, User) or not records:
            continue
        sink = getattr(model, _ADMIN_AUDIT_SINK, None)
        delattr(model, _ADMIN_AUDIT_RECORDS)
        delattr(model, _ADMIN_AUDIT_SINK)
        if sink is None:
            continue
        for record in records:
            _write_admin_audit(sink, session, record)
