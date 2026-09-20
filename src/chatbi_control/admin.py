"""SQLAdmin 管理后台和 ChatBI RBAC（基于角色的访问控制）边界。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from sqlalchemy import func, inspect, select, update
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
from src.authorization.contracts import AuthContext
from src.authorization.passwords import hash_password

from .bootstrap import FIXED_ROLES, normalize_username
from .models import Permission, Role, User, UserSession

FIXED_ROLE_NAMES = frozenset(name for name, _ in FIXED_ROLES)
ADMIN_PERMISSION_NAMES = frozenset({"admin.users", "admin.roles", "admin.audit"})


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
        del request
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
            roles = data.get("roles", model.roles)
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


def mount_admin(
    app: FastAPI,
    *,
    engine: Engine,
    auth_service: AuthService,
    secret_key: str,
    session_factory: Any | None = None,
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
    app.state.sqladmin = admin
    app.state.sqladmin_engine = engine
    return admin


def _revoke_sessions(session: Session, user_id: int) -> None:
    session.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
