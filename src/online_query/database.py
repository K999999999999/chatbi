"""使用 psycopg 以 chatbi_app 只读执行已校验 SQL。"""

from collections.abc import Callable, Mapping
import os
from typing import Any

import psycopg
from psycopg.errors import QueryCanceled

from .contracts import QueryData, ValidatedSQL


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
        try:
            with self._connect(**self._connect_kwargs) as connection:
                connection.read_only = True
                with connection.transaction():
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL statement_timeout = '10s'")
                        cursor.execute(sql.sql)
                        if cursor.description is None:
                            raise DatabaseError("查询未返回结果集")
                        columns = tuple(column.name for column in cursor.description)
                        fetched = cursor.fetchmany(101)
        except QueryCanceled as exc:
            raise DatabaseQueryTimeout("数据库查询超时") from exc
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


def _required(source: Mapping[str, str], name: str) -> str:
    value = source.get(name, "").strip()
    if not value:
        raise DatabaseError(f"缺少 {name} 配置")
    return value
