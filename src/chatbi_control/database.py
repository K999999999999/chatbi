"""ChatBI 应用库连接、创建和可重复迁移。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine

from .bootstrap import control_sql_directory


class ControlDatabaseConfigurationError(RuntimeError):
    """应用库配置缺失或越过数据库边界。"""


class ControlDatabaseMigrationError(RuntimeError):
    """应用库迁移失败。"""


@dataclass(frozen=True)
class ControlDatabaseConfig:
    """应用库和迁移账号配置。"""

    host: str
    port: int
    database: str
    app_user: str
    app_password: str
    migrator_user: str
    migrator_password: str
    bootstrap_database: str = "postgres"

    @classmethod
    def from_environment(
        cls,
        environ: dict[str, str] | None = None,
    ) -> ControlDatabaseConfig:
        values = os.environ if environ is None else environ
        business_database = values.get("POSTGRES_DB", "chatbi_mvp").strip()
        database = values.get("POSTGRES_CONTROL_DB", "chatbi_control").strip()
        app_user = values.get(
            "POSTGRES_CONTROL_APP_USER", "chatbi_control_user"
        ).strip()
        migrator_user = values.get(
            "POSTGRES_CONTROL_MIGRATOR_USER",
            values.get("POSTGRES_MIGRATOR_USER", "chatbi_migrator"),
        ).strip()

        if not database or database == business_database:
            raise ControlDatabaseConfigurationError(
                "POSTGRES_CONTROL_DB 必须是独立于业务库的非空数据库名"
            )
        if app_user in {
            values.get("POSTGRES_APP_USER", "chatbi_app").strip(),
            "chatbi_app",
            migrator_user,
        }:
            raise ControlDatabaseConfigurationError(
                "ChatBI 应用库账号不能复用业务只读账号或迁移账号"
            )

        return cls(
            host=values.get("POSTGRES_HOST", "127.0.0.1").strip(),
            port=_parse_port(values.get("POSTGRES_PORT", "5433")),
            database=database,
            app_user=app_user,
            app_password=_required(values, "POSTGRES_CONTROL_APP_PASSWORD"),
            migrator_user=migrator_user,
            migrator_password=_required(values, "POSTGRES_MIGRATOR_PASSWORD"),
            bootstrap_database=values.get(
                "POSTGRES_CONTROL_BOOTSTRAP_DB", "postgres"
            ).strip()
            or "postgres",
        )

    def connection_kwargs(
        self, *, user: str, password: str, database: str
    ) -> dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": database,
            "user": user,
            "password": password,
            "connect_timeout": 5,
        }

    def app_connection_kwargs(self) -> dict[str, Any]:
        return self.connection_kwargs(
            user=self.app_user,
            password=self.app_password,
            database=self.database,
        )

    def migrator_connection_kwargs(self) -> dict[str, Any]:
        return self.connection_kwargs(
            user=self.migrator_user,
            password=self.migrator_password,
            database=self.database,
        )


def create_control_engine(config: ControlDatabaseConfig) -> Engine:
    """创建只连接 chatbi_control 的 SQLAlchemy Engine。"""

    url = URL.create(
        "postgresql+psycopg",
        username=config.app_user,
        password=config.app_password,
        host=config.host,
        port=config.port,
        database=config.database,
    )
    return create_engine(url, pool_pre_ping=True)


def initialize_control_database(
    config: ControlDatabaseConfig,
    *,
    connect: Any = psycopg.connect,
    sql_directory: Path | None = None,
) -> None:
    """创建应用库、运行时账号和全部幂等迁移。"""

    _ensure_database_and_runtime_role(config, connect=connect)
    directory = control_sql_directory() if sql_directory is None else sql_directory
    migration_files = sorted(directory.glob("*.sql"))
    if not migration_files:
        raise ControlDatabaseMigrationError("应用库迁移目录为空")

    try:
        with connect(**config.migrator_connection_kwargs()) as connection:
            with connection.cursor() as cursor:
                for migration_file in migration_files:
                    statement = migration_file.read_text(encoding="utf-8")
                    cursor.execute(statement)
            connection.commit()
    except Exception as exc:
        raise ControlDatabaseMigrationError(
            "ChatBI 应用库迁移失败，认证和管理入口不得以部分 Schema 启动"
        ) from exc


def _ensure_database_and_runtime_role(
    config: ControlDatabaseConfig, *, connect: Any
) -> None:
    admin_kwargs = config.connection_kwargs(
        user=config.migrator_user,
        password=config.migrator_password,
        database=config.bootstrap_database,
    )
    try:
        with connect(**admin_kwargs) as connection:
            connection.autocommit = True
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (config.database,),
                )
                if cursor.fetchone() is None:
                    cursor.execute(
                        sql.SQL("CREATE DATABASE {}").format(
                            sql.Identifier(config.database)
                        )
                    )
                _ensure_login_role(
                    cursor,
                    config.app_user,
                    config.app_password,
                )
                cursor.execute(
                    sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                        sql.Identifier(config.database),
                        sql.Identifier(config.app_user),
                    )
                )
    except ControlDatabaseMigrationError:
        raise
    except Exception as exc:
        raise ControlDatabaseMigrationError(
            "无法创建 ChatBI 应用库或运行时账号"
        ) from exc


def _ensure_login_role(cursor: Any, username: str, password: str) -> None:
    cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (username,))
    role_exists = cursor.fetchone() is not None
    command = (
        "ALTER ROLE {} WITH LOGIN PASSWORD {}"
        if role_exists
        else "CREATE ROLE {} LOGIN PASSWORD {}"
    )
    cursor.execute(
        sql.SQL(command).format(
            sql.Identifier(username),
            sql.Literal(password),
        )
    )


def _required(environ: dict[str, str], key: str) -> str:
    value = environ.get(key, "").strip()
    if not value:
        raise ControlDatabaseConfigurationError(f"{key} 必须显式设置")
    return value


def _parse_port(value: str) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise ControlDatabaseConfigurationError("POSTGRES_PORT 必须是有效端口") from exc
    if not 1 <= port <= 65535:
        raise ControlDatabaseConfigurationError("POSTGRES_PORT 超出有效范围")
    return port
