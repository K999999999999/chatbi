"""本机管理员恢复装配；不装配Web、LLM或检索资源。"""

import getpass
import os
import sys
import warnings

from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from src.authorization.audit_service import PersistentAuditSink
from src.authorization.auth_service import AuthService
from src.chatbi_control.database import (
    ControlDatabaseConfig,
    create_control_engine,
    verify_control_schema,
)
from src.chatbi_control.username import normalize_username


def recover_admin(username: str, *, environment: str, project: str) -> int:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("管理员恢复需要交互终端；不接受密码参数或流水线输入。", file=sys.stderr)
        return 2
    engine = None
    stage = "输入"
    try:
        username = normalize_username(username)
        print(f"恢复目标：{environment} / {project} / {username}")
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("临时新密码（至少12位）: ")
            confirmation = getpass.getpass("再次输入临时新密码: ")
        if password != confirmation:
            print("两次密码不一致；没有修改账号。", file=sys.stderr)
            return 2
        stage = "Control DB配置与Schema"
        config = ControlDatabaseConfig.from_environment(require_migrator=False)
        forbidden_users = {
            "chatbi_migrator",
            os.environ.get("POSTGRES_MIGRATOR_USER", "chatbi_migrator"),
            os.environ.get("POSTGRES_CONTROL_MIGRATOR_USER", "chatbi_migrator"),
        }
        if config.app_user in forbidden_users:
            raise ValueError("恢复不能使用迁移身份")
        engine = create_control_engine(config)
        with engine.connect() as connection:
            privileged = connection.scalar(
                text(
                    "SELECT rolsuper OR rolcreatedb OR rolcreaterole "
                    "OR has_database_privilege(current_user, current_database(), 'CREATE') "
                    "FROM pg_roles WHERE rolname=current_user"
                )
            )
            if privileged is not False:
                raise ValueError("恢复必须使用应用库运行身份")
        verify_control_schema(engine)
        factory = sessionmaker(engine, expire_on_commit=False)
        stage = "账号校验与恢复事务"
        AuthService(factory, audit_sink=PersistentAuditSink(factory)).recover_admin(
            username, new_password=password, environment=environment, project=project
        )
    except (getpass.GetPassWarning, EOFError):
        print("密码输入无法安全完成；没有修改账号。", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("恢复已中断；未确认成功，不会自动重试。", file=sys.stderr)
        return 130
    except Exception:  # noqa: BLE001 - 连接和事务异常可能携带Secret
        print(f"恢复失败：{stage}；检查目标与配置，不会自动重试。", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()
    print("管理员恢复成功；旧Session已撤销，请用临时密码登录并立即改密。")
    return 0
