"""显式真实浏览器验收：专用账号 + 正式 runtime，退出后禁用验收账号。"""

import os
from contextlib import asynccontextmanager

from sqlalchemy import select

from src.authorization import hash_password
from src.bootstrap.runtime import create_runtime
from src.chatbi_control.models import Role, User
from src.query_api.app import create_app


def create_browser_real_app():
    if os.getenv("CHATBI_REAL_E2E") != "1":
        raise RuntimeError("真实浏览器验收必须显式开启")
    username = os.environ["CHATBI_REAL_E2E_USERNAME"]
    password = os.environ["CHATBI_REAL_E2E_PASSWORD"]
    if not username.startswith("web-e2e-") or len(password) < 32:
        raise RuntimeError("真实验收账号必须为独立临时账号")

    @asynccontextmanager
    async def runtime():
        async with create_runtime() as dependencies:
            sessions = dependencies.admin_session_factory
            with sessions() as session, session.begin():
                if session.scalar(select(User).where(User.username == username)):
                    raise RuntimeError("验收账号已存在，禁止覆盖")
                role = session.scalar(select(Role).where(Role.name == "analyst"))
                if role is None:
                    raise RuntimeError("真实 RBAC 角色尚未初始化")
                user = User(
                    username=username,
                    password_hash=hash_password(password),
                    is_active=True,
                    must_change_password=False,
                    roles=[role],
                )
                session.add(user)
                session.flush()
                user_id = user.id
            try:
                yield dependencies
            finally:
                # 保留账号 / 安全审计 / 分析证据，禁用账号并撤销会话。
                dependencies.auth_service.disable_user(user_id)

    return create_app(runtime_factory=runtime)
