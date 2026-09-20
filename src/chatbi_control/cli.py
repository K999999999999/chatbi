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
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="初始化 ChatBI 应用库和首个管理员")
    parser.add_argument("--username", help="首个管理员用户名；不传时交互输入")
    args = parser.parse_args(argv)

    load_dotenv(override=False)
    username = (args.username or input("首个管理员用户名: ")).strip()
    password = getpass.getpass("首个管理员密码（至少 12 位）: ")
    confirmation = getpass.getpass("再次输入首个管理员密码: ")
    if password != confirmation:
        print("两次密码不一致", file=sys.stderr)
        return 2

    try:
        config = ControlDatabaseConfig.from_environment()
        initialize_control_database(config)
        engine = create_control_engine(config)
        try:
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
    ) as exc:
        print(f"初始化失败：{exc}", file=sys.stderr)
        return 1

    print(f"首个管理员创建成功：{username.lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
