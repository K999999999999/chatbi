"""使用 psycopg 以 chatbi_app 只读执行已校验 SQL。"""

import os
from collections.abc import Callable, Mapping
from contextlib import nullcontext
from typing import Any

import psycopg
from psycopg.errors import QueryCanceled

from src.rag_offline.sources import DEFAULT_STRUCTURE_DIR
from src.structure.runtime_schema import (
    StructureMetadataMismatchError,
    verify_catalog_matches_metadata,
)

from .contracts import ExecutionStopped, QueryData, ValidatedSQL


class DatabaseError(RuntimeError):
    """数据库配置、连接或执行失败。"""


class DatabaseQueryTimeout(DatabaseError):
    """查询超过数据库端 10 秒限制。"""


class PsycopgQueryExecutor:
    """每次查询使用一个显式只读事务，不维护连接池。"""

    def __init__(
        self,
        connect_kwargs: Mapping[str, object],
        *,
        connect: Callable[..., Any] | None = None,
    ) -> None:
        self._connect_kwargs = dict(connect_kwargs)
        self._connect_kwargs.setdefault("connect_timeout", 5)
        self._connect_kwargs["autocommit"] = True
        self._connect = psycopg.connect if connect is None else connect

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        connect: Callable[..., Any] | None = None,
    ) -> "PsycopgQueryExecutor":
        source = os.environ if environ is None else environ
        host = _required(source, "POSTGRES_HOST")
        database = _required(source, "POSTGRES_DB")
        user = _required(source, "POSTGRES_APP_USER")
        password = _required(source, "POSTGRES_APP_PASSWORD")
        if user != "chatbi_app":
            raise DatabaseError("POSTGRES_APP_USER 必须是 chatbi_app")

        try:
            port = int(_required(source, "POSTGRES_PORT"))
        except ValueError:
            raise DatabaseError("POSTGRES_PORT 配置无效") from None
        if not 1 <= port <= 65535:
            raise DatabaseError("POSTGRES_PORT 配置无效")

        return cls(
            {
                "host": host,
                "port": port,
                "dbname": database,
                "user": user,
                "password": password,
                "connect_timeout": 5,
                "autocommit": True,
            },
            connect=connect,
        )

    def execute(self, sql: ValidatedSQL) -> QueryData:
        return self.execute_with_control(sql, None)

    def execute_with_control(self, sql: ValidatedSQL, execution_control) -> QueryData:
        try:
            if execution_control is not None:
                execution_control.checkpoint()
            with self._connect(**self._connect_kwargs) as connection:
                connection.read_only = True
                with connection.transaction():
                    cancel_scope = (
                        execution_control.register_database_cancel(
                            lambda: connection.cancel_safe(timeout=1.0)
                        )
                        if execution_control is not None
                        else nullcontext()
                    )
                    with cancel_scope, connection.cursor() as cursor:
                        if execution_control is not None:
                            execution_control.checkpoint()
                        cursor.execute("SET LOCAL statement_timeout = '10s'")
                        cursor.execute(sql.sql)
                        if cursor.description is None:
                            raise DatabaseError("查询未返回结果集")
                        columns = tuple(column.name for column in cursor.description)
                        fetched = cursor.fetchmany(101)
                        if execution_control is not None:
                            execution_control.checkpoint()
        except QueryCanceled as exc:
            if execution_control is not None:
                execution_control.checkpoint()
            raise DatabaseQueryTimeout("数据库查询超时") from exc
        except ExecutionStopped:
            raise
        except DatabaseError:
            raise
        except Exception as exc:
            raise DatabaseError("数据库连接或执行失败") from exc

        rows = tuple(tuple(row) for row in fetched[:100])
        return QueryData(
            columns=columns,
            rows=rows,
            truncated=len(fetched) > 100,
        )

    def verify_structure_metadata(self) -> None:
        """Compare the live catalog with generated metadata using this DB identity."""

        try:
            with self._connect(**self._connect_kwargs) as connection:
                connection.read_only = True
                verify_catalog_matches_metadata(connection, DEFAULT_STRUCTURE_DIR)
        except (DatabaseError, StructureMetadataMismatchError):
            raise
        except psycopg.Error as exc:
            raise DatabaseError(
                "无法验证 PostgreSQL Schema 与 Structure Metadata"
            ) from exc


def _required(source: Mapping[str, str], name: str) -> str:
    value = source.get(name, "").strip()
    if not value:
        raise DatabaseError(f"缺少 {name} 配置")
    return value
