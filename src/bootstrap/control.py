"""ChatBI 应用库迁移和首个管理员 CLI。"""

from __future__ import annotations

import getpass
import sys
from contextlib import ExitStack

from sqlalchemy.orm import Session

from src.chatbi_control.bootstrap import BootstrapError, create_first_admin
from src.chatbi_control.database import (
    ControlDatabaseConfig,
    ControlDatabaseConfigurationError,
    ControlDatabaseMigrationError,
    create_control_engine,
    initialize_control_database,
    verify_control_schema,
)

from .lifecycle import register_cleanup


def migrate() -> int:
    try:
        config = ControlDatabaseConfig.from_environment()
        initialize_control_database(config)
    except (
        ControlDatabaseConfigurationError,
        ControlDatabaseMigrationError,
    ) as exc:
        print(f"应用库迁移失败：{exc}", file=sys.stderr)
        return 1

    print("应用库 Schema 和固定 RBAC migration 已完成；没有创建管理员。")
    return 0


def create_admin(username: str | None = None) -> int:
    username = (username or input("首个管理员用户名: ")).strip()
    password = getpass.getpass("首个管理员密码（至少 12 位）: ")
    confirmation = getpass.getpass("再次输入首个管理员密码: ")
    if password != confirmation:
        print("两次密码不一致", file=sys.stderr)
        return 2

    try:
        config = ControlDatabaseConfig.from_environment(require_migrator=False)
        engine = create_control_engine(config)
        with ExitStack() as resources:
            register_cleanup(resources, "admin_database", engine.dispose)
            verify_control_schema(engine)
            with Session(engine) as session, session.begin():
                create_first_admin(
                    session,
                    username=username,
                    password=password,
                )
    except (
        BootstrapError,
        ControlDatabaseConfigurationError,
        ControlDatabaseMigrationError,
        ValueError,
    ) as exc:
        print(f"首个管理员创建失败：{exc}", file=sys.stderr)
        return 1

    print(f"首个管理员创建成功：{username.lower()}")
    return 0
