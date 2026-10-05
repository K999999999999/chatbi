"""ChatBI 应用库连接、创建和可重复迁移。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, Engine

from .bootstrap import control_sql_directory


class ControlDatabaseConfigurationError(RuntimeError):
    """应用库配置缺失或越过数据库边界。"""


class ControlDatabaseMigrationError(RuntimeError):
    """应用库迁移失败。"""


CONTROL_SCHEMA_VERSION = "chatbi-control-v5"


@dataclass(frozen=True)
class ControlDatabaseConfig:
    """应用库和迁移账号配置。"""

    host: str
    port: int
    database: str
    app_user: str
    app_password: str = field(repr=False)
    migrator_user: str
    migrator_password: str = field(repr=False)
    bootstrap_database: str = "postgres"

    @classmethod
    def from_environment(
        cls,
        environ: dict[str, str] | None = None,
        *,
        require_migrator: bool = True,
    ) -> ControlDatabaseConfig:
        values = os.environ if environ is None else environ
        business_database = values.get("POSTGRES_DB", "chatbi_mvp").strip()
        database = values.get("POSTGRES_CONTROL_DB", "chatbi_control").strip()
        app_user = values.get(
            "POSTGRES_CONTROL_APP_USER", "chatbi_control_user"
        ).strip()
        migrator_user = (
            values.get(
                "POSTGRES_CONTROL_MIGRATOR_USER",
                values.get("POSTGRES_MIGRATOR_USER", "chatbi_migrator"),
            ).strip()
            if require_migrator
            else ""
        )

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
            migrator_password=(
                _required(values, "POSTGRES_MIGRATOR_PASSWORD")
                if require_migrator
                else ""
            ),
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


def verify_control_schema(engine: Engine) -> None:
    """确认运行时账号看到的是完整的 ChatBI 应用库版本。"""

    try:
        with engine.connect() as connection:
            versions = set(
                connection.execute(
                    text("SELECT version FROM schema_migrations")
                ).scalars()
            )
    except Exception as exc:
        raise ControlDatabaseMigrationError(
            "ChatBI 应用库 Schema 不可用，请先使用 chatbi_migrator 完成迁移"
        ) from exc
    if CONTROL_SCHEMA_VERSION not in versions:
        raise ControlDatabaseMigrationError(
            "ChatBI 应用库 Schema 版本不完整，请先使用 chatbi_migrator 完成迁移"
        )
    try:
        with engine.connect() as connection:
            if connection.dialect.name == "postgresql":
                checkpoint_ready = connection.execute(
                    text(
                        """
                        SELECT
                            to_regclass('public.checkpoints') IS NOT NULL
                            AND to_regclass('public.checkpoint_blobs') IS NOT NULL
                            AND to_regclass('public.checkpoint_writes') IS NOT NULL
                            AND to_regclass('public.checkpoint_migrations') IS NOT NULL
                            AND EXISTS (SELECT 1 FROM checkpoint_migrations)
                            AND has_table_privilege(current_user, 'checkpoint_migrations', 'SELECT')
                            AND has_table_privilege(current_user, 'checkpoints', 'SELECT')
                            AND has_table_privilege(current_user, 'checkpoints', 'INSERT')
                            AND has_table_privilege(current_user, 'checkpoints', 'UPDATE')
                            AND has_table_privilege(current_user, 'checkpoints', 'DELETE')
                            AND has_table_privilege(current_user, 'checkpoint_blobs', 'SELECT')
                            AND has_table_privilege(current_user, 'checkpoint_blobs', 'INSERT')
                            AND has_table_privilege(current_user, 'checkpoint_blobs', 'UPDATE')
                            AND has_table_privilege(current_user, 'checkpoint_blobs', 'DELETE')
                            AND has_table_privilege(current_user, 'checkpoint_writes', 'SELECT')
                            AND has_table_privilege(current_user, 'checkpoint_writes', 'INSERT')
                            AND has_table_privilege(current_user, 'checkpoint_writes', 'UPDATE')
                            AND has_table_privilege(current_user, 'checkpoint_writes', 'DELETE')
                        """
                    )
                ).scalar_one()
            else:
                table_names = set(inspect(connection).get_table_names())
                checkpoint_ready = {
                    "checkpoints",
                    "checkpoint_blobs",
                    "checkpoint_writes",
                    "checkpoint_migrations",
                }.issubset(table_names)
                if checkpoint_ready:
                    checkpoint_ready = connection.execute(
                        text("SELECT EXISTS (SELECT 1 FROM checkpoint_migrations)")
                    ).scalar_one()
    except Exception as exc:
        raise ControlDatabaseMigrationError(
            "经营分析 checkpoint Schema 或运行权限未安装，请先运行 migration"
        ) from exc
    if not checkpoint_ready:
        raise ControlDatabaseMigrationError(
            "经营分析 checkpoint Schema 或运行权限未安装，请先运行 migration"
        )
    _verify_history_schema(engine)


def _verify_history_schema(engine: Engine) -> None:
    required = {
        "history_records": {
            "id",
            "owner_user_id",
            "kind",
            "creation_operation_id",
            "context_revision",
            "record_revision",
            "active_turn_id",
            "last_success_turn_id",
            "execution_generation",
            "deleted_at",
            "title",
            "first_question",
            "creation_operation_hash",
            "created_at",
            "updated_at",
            "next_ordinal",
            "analysis_run_id",
        },
        "history_turns": {
            "id",
            "history_id",
            "operation_id",
            "status",
            "snapshot",
            "runtime_epoch",
            "execution_generation",
            "ordinal",
            "operation_hash",
            "question",
            "request_id",
            "created_at",
            "completed_at",
            "public_error",
            "attempt_input",
            "snapshot_version",
        },
        "saved_results": {
            "id",
            "owner_user_id",
            "snapshot",
            "snapshot_version",
            "record_revision",
            "kind",
            "title",
            "created_at",
            "updated_at",
            "source_history_id",
            "source_turn_id",
        },
        "history_runtime": {"singleton", "runtime_epoch"},
        "history_executions": {
            "id",
            "owner_user_id",
            "history_id",
            "turn_id",
            "operation_id",
            "request_hash",
            "mode",
            "operation_kind",
            "status",
            "stop_reason",
            "runtime_epoch",
            "execution_generation",
            "created_at",
            "started_at",
            "deadline_at",
            "stop_requested_at",
            "finished_at",
            "public_error",
        },
    }
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            tables = set(inspector.get_table_names())
            if not set(required).issubset(tables):
                raise ValueError("历史对象缺失")
            for table, columns in required.items():
                if not columns.issubset(
                    {c["name"] for c in inspector.get_columns(table)}
                ):
                    raise ValueError("历史字段缺失")
            if connection.dialect.name == "postgresql":
                constraints = inspector.get_foreign_keys("history_records")
                if not {"history_active_turn_fk", "history_success_turn_fk"}.issubset(
                    {c["name"] for c in constraints}
                ):
                    raise ValueError("历史引用约束缺失")
                unique = {
                    tuple(c["column_names"])
                    for c in inspector.get_unique_constraints("history_records")
                }
                if ("owner_user_id", "creation_operation_id") not in unique:
                    raise ValueError("历史受理唯一约束缺失")
                turn_unique = {
                    tuple(c["column_names"])
                    for c in inspector.get_unique_constraints("history_turns")
                }
                if not {
                    ("history_id", "ordinal"),
                    ("history_id", "operation_id"),
                    ("history_id", "id"),
                }.issubset(turn_unique):
                    raise ValueError("历史轮次唯一约束缺失")
                if ("analysis_run_id",) not in unique:
                    raise ValueError("分析运行唯一约束缺失")
                execution_unique = {
                    tuple(c["column_names"])
                    for c in inspector.get_unique_constraints("history_executions")
                }
                if not {
                    ("owner_user_id", "operation_id"),
                    ("history_id", "turn_id"),
                }.issubset(execution_unique):
                    raise ValueError("执行身份唯一约束缺失")
                execution_fks = inspector.get_foreign_keys("history_executions")
                execution_fks_by_name = {item["name"]: item for item in execution_fks}
                execution_fk_names = {
                    "history_execution_owner_history_fk",
                    "history_execution_history_turn_fk",
                }
                if not execution_fk_names.issubset(execution_fks_by_name):
                    raise ValueError("执行归属 / 轮次约束缺失")
                if any(
                    execution_fks_by_name[name].get("options", {}).get("ondelete")
                    != "CASCADE"
                    for name in execution_fk_names
                ):
                    raise ValueError("执行元数据级联删除约束缺失")
                for table, name in (
                    ("history_records", "history_records_owner_updated_idx"),
                    ("saved_results", "saved_results_owner_updated_idx"),
                    ("history_executions", "history_executions_owner_created_idx"),
                ):
                    if name not in {
                        index["name"] for index in inspector.get_indexes(table)
                    }:
                        raise ValueError("历史列表索引缺失")
                checks = {
                    "history_records": {
                        "history_record_kind",
                        "history_context_revision",
                        "history_record_revision",
                        "history_next_ordinal",
                        "history_generation",
                        "history_analysis_identity",
                    },
                    "history_turns": {
                        "history_turn_ordinal",
                        "history_turn_status",
                        "history_turn_success_snapshot",
                        "history_turn_snapshot_version",
                    },
                    "saved_results": {
                        "saved_kind",
                        "saved_revision",
                        "saved_snapshot_version",
                    },
                    "history_runtime": {"history_singleton"},
                    "history_executions": {
                        "history_execution_mode",
                        "history_execution_operation_kind",
                        "history_execution_status",
                        "history_execution_generation",
                    },
                }
                for table, names in checks.items():
                    if not names.issubset(
                        {c["name"] for c in inspector.get_check_constraints(table)}
                    ):
                        raise ValueError("历史状态约束缺失")
                for table in ("history_records", "saved_results"):
                    if not any(
                        c["constrained_columns"] == ["owner_user_id"]
                        and c["referred_table"] == "users"
                        and c["referred_columns"] == ["id"]
                        for c in inspector.get_foreign_keys(table)
                    ):
                        raise ValueError("历史归属约束缺失")
                for table in required:
                    privileges = (
                        ("SELECT", "INSERT", "UPDATE")
                        if table == "history_runtime"
                        else ("SELECT", "INSERT", "UPDATE", "DELETE")
                    )
                    for privilege in privileges:
                        if not connection.execute(
                            text(
                                "SELECT has_table_privilege(current_user, :table, :privilege)"
                            ),
                            {"table": table, "privilege": privilege},
                        ).scalar_one():
                            raise ValueError("历史权限缺失")
    except Exception as exc:
        raise ControlDatabaseMigrationError(
            "历史Schema或权限不完整，请先运行migration"
        ) from exc


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
        _install_analysis_checkpoints(config, connect=connect)
    except Exception as exc:
        raise ControlDatabaseMigrationError(
            "ChatBI 应用库迁移失败，认证和管理入口不得以部分 Schema 启动"
        ) from exc


def _install_analysis_checkpoints(
    config: ControlDatabaseConfig,
    *,
    connect: Any,
) -> None:
    """由迁移账号安装 LangGraph 版本化 checkpoint schema 和最小运行权限。"""

    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row

    try:
        with connect(
            **config.migrator_connection_kwargs(),
            autocommit=True,
            row_factory=dict_row,
        ) as connection:
            PostgresSaver(connection).setup()
            with connection.cursor() as cursor:
                for table in (
                    "checkpoints",
                    "checkpoint_blobs",
                    "checkpoint_writes",
                ):
                    cursor.execute(
                        sql.SQL(
                            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {} TO {}"
                        ).format(
                            sql.Identifier(table),
                            sql.Identifier(config.app_user),
                        )
                    )
                cursor.execute(
                    sql.SQL("GRANT SELECT ON TABLE {} TO {}").format(
                        sql.Identifier("checkpoint_migrations"),
                        sql.Identifier(config.app_user),
                    )
                )
    except Exception as exc:
        raise ControlDatabaseMigrationError(
            "经营分析 checkpoint Schema 或运行权限安装失败"
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
