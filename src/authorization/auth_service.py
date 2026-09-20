"""ChatBI 内置账号认证和数据库 Session Service。"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.chatbi_control.bootstrap import normalize_username
from src.chatbi_control.models import User, UserSession

from .contracts import AuthContext
from .audit_service import AuditRecord, AuditUnavailable
from .passwords import hash_password, verify_password

IDLE_TTL = timedelta(minutes=30)
ABSOLUTE_TTL = timedelta(hours=8)
MAX_FAILED_LOGIN_ATTEMPTS = 5
FAILED_LOGIN_LOCK_DURATION = timedelta(minutes=15)


class AuthenticationFailed(RuntimeError):
    """凭证无效、用户禁用或登录被临时锁定。"""


class SessionExpired(AuthenticationFailed):
    """Session 不存在、已撤销、已过期或用户已禁用。"""


class AuthService:
    """共享给普通用户端和管理后台的账号生命周期服务。"""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        clock: Callable[[], datetime] | None = None,
        token_factory: Callable[[], str] | None = None,
        audit_sink: object | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock or (lambda: datetime.now(UTC))
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(32))
        self._audit_sink = audit_sink

    def login(
        self,
        username: str,
        password: str,
        *,
        request_id: str | None = None,
    ) -> LoginResult:
        """验证凭证并创建数据库 Session。"""

        try:
            normalized_username = normalize_username(username)
        except (TypeError, ValueError):
            raise AuthenticationFailed("用户名或密码错误") from None

        now = _as_utc(self._clock())
        login_failed = False
        failure_reason = "INVALID_CREDENTIALS"
        raw_token = ""
        context: AuthContext | None = None
        with self._session_factory() as session, session.begin():
            user = session.scalar(
                select(User).where(User.username == normalized_username)
            )
            if (
                user is None
                or not user.is_active
                or (user.locked_until is not None and _as_utc(user.locked_until) > now)
            ):
                login_failed = True
                failure_reason = (
                    "USER_DISABLED"
                    if user is not None and not user.is_active
                    else "LOGIN_LOCKED"
                    if user is not None and user.locked_until is not None
                    else "INVALID_CREDENTIALS"
                )
            elif not verify_password(password, user.password_hash):
                user.failed_login_count += 1
                if user.failed_login_count >= MAX_FAILED_LOGIN_ATTEMPTS:
                    user.locked_until = now + FAILED_LOGIN_LOCK_DURATION
                login_failed = True
                failure_reason = "INVALID_CREDENTIALS"
            else:
                user.failed_login_count = 0
                user.locked_until = None
                raw_token = self._new_token()
                session.add(
                    UserSession(
                        token_hash=_hash_token(raw_token),
                        user_id=user.id,
                        created_at=now,
                        last_seen_at=now,
                        expires_at=now + IDLE_TTL,
                        absolute_expires_at=now + ABSOLUTE_TTL,
                    )
                )
                context = _context_for_user(user)

            if login_failed:
                self._write_security_audit(
                    session,
                    AuditRecord(
                        event_type="auth.login",
                        target_type="user",
                        target_id=normalized_username,
                        outcome="failure",
                        request_id=request_id,
                        reason=failure_reason,
                        actor_user_id=user.id if user is not None else None,
                    ),
                )
            else:
                self._write_security_audit(
                    session,
                    AuditRecord(
                        event_type="auth.login",
                        target_type="user",
                        target_id=normalized_username,
                        outcome="success",
                        request_id=request_id,
                        reason="AUTHENTICATED",
                        actor_user_id=user.id if user is not None else None,
                    ),
                )

        if login_failed or context is None:
            raise AuthenticationFailed("用户名或密码错误")

        return LoginResult(token=raw_token, auth_context=context)

    def authenticate_session(self, raw_token: str) -> AuthContext:
        """校验 Session，并在有效请求上滑动 Idle TTL。"""

        token_hash = _hash_token_or_raise(raw_token)
        now = _as_utc(self._clock())
        with self._session_factory() as session, session.begin():
            record = session.scalar(
                select(UserSession).where(UserSession.token_hash == token_hash)
            )
            if record is None or record.revoked_at is not None:
                raise SessionExpired("Session 已失效")
            if not record.user.is_active:
                raise SessionExpired("Session 已失效")
            if now >= _as_utc(record.expires_at) or now >= _as_utc(
                record.absolute_expires_at
            ):
                record.revoked_at = now
                raise SessionExpired("Session 已失效")

            record.last_seen_at = now
            record.expires_at = min(now + IDLE_TTL, _as_utc(record.absolute_expires_at))
            return _context_for_user(record.user)

    def logout(self, raw_token: str, *, request_id: str | None = None) -> bool:
        """撤销当前 Session；未知或已撤销 Token 视为幂等成功。"""

        token_hash = _hash_token_or_raise(raw_token)
        now = _as_utc(self._clock())
        with self._session_factory() as session, session.begin():
            record = session.scalar(
                select(UserSession).where(UserSession.token_hash == token_hash)
            )
            if record is None or record.revoked_at is not None:
                return False
            record.revoked_at = now
            self._write_security_audit(
                session,
                AuditRecord(
                    event_type="auth.logout",
                    target_type="session",
                    target_id=str(record.user_id),
                    outcome="success",
                    request_id=request_id,
                    reason="LOGOUT",
                    actor_user_id=record.user_id,
                ),
            )
            return True

    def change_password(
        self,
        raw_token: str,
        *,
        current_password: str,
        new_password: str,
        request_id: str | None = None,
    ) -> None:
        """修改当前用户密码，并撤销该用户全部旧 Session。"""

        token_hash = _hash_token_or_raise(raw_token)
        now = _as_utc(self._clock())
        new_hash = hash_password(new_password)
        with self._session_factory() as session, session.begin():
            record = self._valid_record(session, token_hash, now)
            if not verify_password(current_password, record.user.password_hash):
                raise AuthenticationFailed("用户名或密码错误")
            record.user.password_hash = new_hash
            record.user.must_change_password = False
            record.user.failed_login_count = 0
            record.user.locked_until = None
            record.user.updated_at = now
            _revoke_user_sessions(session, record.user.id, now)
            self._write_security_audit(
                session,
                AuditRecord(
                    event_type="auth.password_change",
                    target_type="user",
                    target_id=str(record.user.id),
                    outcome="success",
                    request_id=request_id,
                    reason="PASSWORD_CHANGED",
                    actor_user_id=record.user.id,
                ),
            )

    def reset_password(
        self,
        user_id: int,
        *,
        new_password: str,
        actor_user_id: int | None = None,
        request_id: str | None = None,
    ) -> None:
        """管理员重置用户密码，并撤销该用户全部旧 Session。"""

        new_hash = hash_password(new_password)
        now = _as_utc(self._clock())
        with self._session_factory() as session, session.begin():
            user = session.get(User, user_id)
            if user is None:
                raise AuthenticationFailed("用户不存在")
            user.password_hash = new_hash
            user.must_change_password = True
            user.failed_login_count = 0
            user.locked_until = None
            user.updated_at = now
            _revoke_user_sessions(session, user.id, now)
            self._write_security_audit(
                session,
                AuditRecord(
                    event_type="auth.password_reset",
                    target_type="user",
                    target_id=str(user.id),
                    outcome="success",
                    request_id=request_id,
                    reason="PASSWORD_RESET",
                    actor_user_id=actor_user_id,
                ),
            )

    def disable_user(
        self,
        user_id: int,
        *,
        actor_user_id: int | None = None,
        request_id: str | None = None,
    ) -> None:
        """禁用用户并立即撤销其全部 Session。"""

        now = _as_utc(self._clock())
        with self._session_factory() as session, session.begin():
            user = session.get(User, user_id)
            if user is None:
                raise AuthenticationFailed("用户不存在")
            user.is_active = False
            user.updated_at = now
            _revoke_user_sessions(session, user.id, now)
            self._write_security_audit(
                session,
                AuditRecord(
                    event_type="user.disable",
                    target_type="user",
                    target_id=str(user.id),
                    outcome="success",
                    request_id=request_id,
                    reason="USER_DISABLED",
                    actor_user_id=actor_user_id,
                ),
            )

    def enable_user(
        self,
        user_id: int,
        *,
        actor_user_id: int | None = None,
        request_id: str | None = None,
    ) -> None:
        """启用用户；启用不自动创建 Session。"""

        now = _as_utc(self._clock())
        with self._session_factory() as session, session.begin():
            user = session.get(User, user_id)
            if user is None:
                raise AuthenticationFailed("用户不存在")
            user.is_active = True
            user.updated_at = now
            self._write_security_audit(
                session,
                AuditRecord(
                    event_type="user.enable",
                    target_type="user",
                    target_id=str(user.id),
                    outcome="success",
                    request_id=request_id,
                    reason="USER_ENABLED",
                    actor_user_id=actor_user_id,
                ),
            )

    @staticmethod
    def can_execute_query(auth_context: AuthContext) -> bool:
        """首次登录未改密时，即使拥有角色也不能执行查询。"""

        return (
            not auth_context.must_change_password
            and "query.execute" in auth_context.permissions
        )

    @staticmethod
    def _valid_record(session: Session, token_hash: str, now: datetime) -> UserSession:
        record = session.scalar(
            select(UserSession).where(UserSession.token_hash == token_hash)
        )
        if record is None or record.revoked_at is not None or not record.user.is_active:
            raise SessionExpired("Session 已失效")
        if now >= _as_utc(record.expires_at) or now >= _as_utc(
            record.absolute_expires_at
        ):
            record.revoked_at = now
            raise SessionExpired("Session 已失效")
        return record

    def _new_token(self) -> str:
        raw_token = self._token_factory()
        if not isinstance(raw_token, str) or not raw_token:
            raise RuntimeError("Session Token 生成失败")
        return raw_token

    def _write_security_audit(self, session: Session, record: AuditRecord) -> None:
        if self._audit_sink is None:
            return
        writer = getattr(self._audit_sink, "write", None)
        if not callable(writer):
            raise AuditUnavailable("ChatBI 审计 Sink 不支持事务内写入")
        try:
            writer(session, record)
        except AuditUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - security audit must Fail Closed
            raise AuditUnavailable("ChatBI 审计写入失败") from exc


class LocalSessionIdentityProvider:
    """从 Bearer Header 校验 ChatBI 自有数据库 Session。"""

    identity_provider = "local"

    def __init__(self, auth_service: AuthService) -> None:
        self._auth_service = auth_service

    def authenticate(self, provider_input: object | None = None) -> AuthContext:
        headers = getattr(provider_input, "headers", None)
        authorization = headers.get("Authorization", "") if headers is not None else ""
        scheme, separator, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not separator or not token.strip():
            from .contracts import AuthenticationRequired

            raise AuthenticationRequired("需要有效的身份认证")
        try:
            return self._auth_service.authenticate_session(token.strip())
        except SessionExpired as exc:
            from .contracts import AuthenticationRequired

            raise AuthenticationRequired("需要有效的身份认证") from exc
        except Exception as exc:  # noqa: BLE001 - identity must Fail Closed
            from .contracts import IdentityProviderUnavailable

            raise IdentityProviderUnavailable("本地 Session 暂时不可用") from exc


class LoginResult:
    """登录成功后短暂返回给边缘适配器的原始 Token 和身份。"""

    def __init__(self, *, token: str, auth_context: AuthContext) -> None:
        self.token = token
        self.auth_context = auth_context


def _context_for_user(user: User) -> AuthContext:
    permissions = frozenset(
        permission.name for role in user.roles for permission in role.permissions
    )
    return AuthContext(
        subject_id=user.username,
        identity_provider="local",
        user_id=user.id,
        username=user.username,
        permissions=permissions,
        must_change_password=user.must_change_password,
    )


def _revoke_user_sessions(session: Session, user_id: int, now: datetime) -> None:
    session.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _hash_token_or_raise(raw_token: str) -> str:
    if not isinstance(raw_token, str) or not raw_token:
        raise SessionExpired("Session 已失效")
    return _hash_token(raw_token)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
