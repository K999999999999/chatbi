"""ChatBI 应用库 Schema（模式）和首个管理员初始化。"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.authorization.passwords import hash_password

from .models import Permission, Role, User
from .username import normalize_username

FIXED_PERMISSIONS: tuple[tuple[str, str], ...] = (
    ("query.execute", "执行 ChatBI 查询"),
    ("admin.users", "管理 ChatBI 用户"),
    ("admin.roles", "管理 ChatBI 角色和权限"),
    ("admin.audit", "查看 ChatBI 审计记录"),
)

FIXED_ROLES: tuple[tuple[str, str], ...] = (
    ("admin", "ChatBI 管理员"),
    ("analyst", "ChatBI 查询用户"),
)


class BootstrapError(RuntimeError):
    """应用库初始化失败。"""


def seed_rbac(session: Session) -> Mapping[str, Role]:
    """幂等写入固定角色和权限目录。"""

    roles: dict[str, Role] = {}
    for name, description in FIXED_ROLES:
        role = session.scalar(select(Role).where(Role.name == name))
        if role is None:
            role = Role(name=name, description=description)
            session.add(role)
        else:
            role.description = description
        roles[name] = role

    permissions: dict[str, Permission] = {}
    for name, description in FIXED_PERMISSIONS:
        permission = session.scalar(select(Permission).where(Permission.name == name))
        if permission is None:
            permission = Permission(name=name, description=description)
            session.add(permission)
        else:
            permission.description = description
        permissions[name] = permission

    session.flush()
    roles["admin"].permissions = list(permissions.values())
    roles["analyst"].permissions = [permissions["query.execute"]]
    return roles


def create_first_admin(session: Session, *, username: str, password: str) -> User:
    """只允许在尚无管理员时创建首个管理员。"""

    normalized_username = normalize_username(username)
    existing_admin = session.scalar(
        select(User).join(User.roles).where(Role.name == "admin").limit(1)
    )
    if existing_admin is not None:
        raise BootstrapError("首个管理员已经初始化，不能重复执行")

    roles = seed_rbac(session)
    user = User(
        username=normalized_username,
        password_hash=hash_password(password),
        is_active=True,
        must_change_password=True,
        roles=[roles["admin"]],
    )
    session.add(user)
    session.flush()
    return user


def control_sql_directory() -> Path:
    """返回应用库 SQL 迁移目录。"""

    return Path(__file__).resolve().parents[2] / "database" / "control"
