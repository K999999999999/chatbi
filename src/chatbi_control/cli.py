"""ChatBI 应用库迁移和首个管理员 CLI。"""

from __future__ import annotations

import argparse
import getpass
import sys

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from .bootstrap import BootstrapError, create_first_admin
from .database import (
    ControlDatabaseConfig,
    ControlDatabaseConfigurationError,
    ControlDatabaseMigrationError,
    create_control_engine,
    initialize_control_database,
    verify_control_schema,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="迁移 ChatBI 应用库或显式创建首个管理员"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "migrate", help="创建应用库并运行可重复的 Schema / RBAC migration"
    )
    admin_parser = commands.add_parser("create-admin", help="交互式创建首个管理员")
    admin_parser.add_argument("--username", help="首个管理员用户名；不传时交互输入")
    args = parser.parse_args(argv)

    load_dotenv(override=False)

    if args.command == "migrate":
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

    username = (args.username or input("首个管理员用户名: ")).strip()
    password = getpass.getpass("首个管理员密码（至少 12 位）: ")
    confirmation = getpass.getpass("再次输入首个管理员密码: ")
    if password != confirmation:
        print("两次密码不一致", file=sys.stderr)
        return 2

    try:
        config = ControlDatabaseConfig.from_environment(require_migrator=False)
        engine = create_control_engine(config)
        try:
            verify_control_schema(engine)
            with Session(engine) as session, session.begin():
                create_first_admin(
                    session,
                    username=username,
                    password=password,
                )
        finally:
            engine.dispose()
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


if __name__ == "__main__":
    raise SystemExit(main())
