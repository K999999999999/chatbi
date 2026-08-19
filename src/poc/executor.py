"""只读 PostgreSQL Query Executor（查询执行器）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import psycopg

from scripts.metadata.export_schema import load_env
from src.poc.sql_guard import ValidatedSql


class QueryExecutionError(RuntimeError):
    """查询执行失败或结果超过 POC 上限。"""


@dataclass(frozen=True)
class QueryResult:
    """数据库返回的列和行。"""

    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]


class QueryExecutor:
    """使用 chatbi_app、只读事务和执行超时访问 PostgreSQL。"""

    def __init__(
        self,
        connection_config: dict[str, Any],
        *,
        max_rows: int = 100,
        connect: Callable[..., Any] = psycopg.connect,
    ) -> None:
        if max_rows <= 0:
            raise ValueError("max_rows 必须大于 0")
        self.connection_config = dict(connection_config)
        self.max_rows = max_rows
        self._connect = connect

    @classmethod
    def from_env(
        cls,
        env_file: Path,
        *,
        max_rows: int = 100,
        statement_timeout_ms: int = 5000,
    ) -> "QueryExecutor":
        env = load_env(env_file)
        required = ("POSTGRES_APP_USER", "POSTGRES_APP_PASSWORD")
        missing = [key for key in required if not env.get(key)]
        if missing:
            raise QueryExecutionError(
                f".env 缺少应用只读账号配置：{', '.join(missing)}"
            )
        if statement_timeout_ms <= 0:
            raise ValueError("statement_timeout_ms 必须大于 0")
        return cls(
            {
                "host": env.get("POSTGRES_HOST", "127.0.0.1"),
                "port": int(env.get("POSTGRES_PORT", "5432")),
                "dbname": env.get("POSTGRES_DB", "chatbi_mvp"),
                "user": env["POSTGRES_APP_USER"],
                "password": env["POSTGRES_APP_PASSWORD"],
                "options": (
                    "-c default_transaction_read_only=on "
                    f"-c statement_timeout={statement_timeout_ms}"
                ),
                "connect_timeout": 10,
            },
            max_rows=max_rows,
        )

    def execute(self, sql: ValidatedSql) -> QueryResult:
        """执行已通过 Guard 的 SQL，不接受普通字符串。"""

        try:
            with self._connect(**self.connection_config) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql.sql)
                    description = cursor.description or ()
                    columns = tuple(str(item.name) for item in description)
                    rows = tuple(cursor.fetchmany(self.max_rows + 1))
                    if len(rows) > self.max_rows:
                        raise QueryExecutionError(
                            f"查询结果超过 {self.max_rows} 行上限"
                        )
                    return QueryResult(columns=columns, rows=rows)
        except QueryExecutionError:
            raise
        except psycopg.Error as exc:
            state = getattr(exc, "sqlstate", None) or "unknown"
            raise QueryExecutionError(f"查询执行失败（SQLSTATE={state}）") from exc
