"""显式初始化命令分发；按所选操作加载依赖。"""

import argparse
from pathlib import Path

from dotenv import load_dotenv


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.bootstrap", description="ChatBI 初始化资源"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="幂等安装应用库、RBAC 和 checkpoint")
    admin = commands.add_parser("create-admin", help="交互式创建首个管理员")
    admin.add_argument("--username", help="首个管理员用户名；不传时交互输入")
    recovery = commands.add_parser("recover-admin", help="可信本机交互恢复启用管理员")
    recovery.add_argument("--username", required=True)
    recovery.add_argument("--environment", choices=("dev", "app"), required=True)
    recovery.add_argument("--project", required=True)
    commands.add_parser("prepare-model", help="准备固定版本 Embedding 模型")
    rag = commands.add_parser("build-rag", help="构建、验证并发布 RAG 资产")
    rag.add_argument("--structure-dir", type=Path)
    rag.add_argument("--metrics-path", type=Path)
    rag.add_argument("--output-dir", type=Path)
    rag.add_argument("--build-id")
    commands.add_parser("verify", help="只读检查标准容器初始化与运行资产")
    args = parser.parse_args(argv)
    load_dotenv(override=False)

    if args.command == "recover-admin":
        from .admin_recovery import recover_admin

        return recover_admin(
            args.username, environment=args.environment, project=args.project
        )

    if args.command == "verify":
        from .verification import verify

        return verify()

    if args.command == "migrate":
        from .control import migrate

        return migrate()
    if args.command == "create-admin":
        from .control import create_admin

        return create_admin(args.username)
    if args.command == "prepare-model":
        from .model import prepare_model

        return prepare_model()
    from .rag import build_rag

    return build_rag(args)
