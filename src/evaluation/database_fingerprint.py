"""Stable summaries and hashes for the local Sales Mart evaluation database."""

import hashlib
import json
import os
from collections.abc import Callable, Mapping
from typing import Any

import psycopg

from .reporting import (
    SALES_MART_DATA_HASH_ALGORITHM,
    SalesMartDataFingerprint,
    _canonical_value,
)
from .reporting_errors import ReportingError


class SalesMartFingerprintError(ReportingError):
    """The local Sales Mart state could not be read safely for an evaluation."""


_SALES_MART_TABLES = (
    ("dim_date", ("date_key",)),
    ("dim_customer", ("customer_key",)),
    ("dim_product", ("product_key",)),
    ("dim_sales_region", ("sales_region_key",)),
    ("dim_currency", ("currency_key",)),
    ("fct_exchange_rate_daily", ("rate_date_key", "currency_key")),
    ("fct_sales_order_line", ("sales_order_line_key",)),
)


def collect_sales_mart_fingerprint(
    environ: Mapping[str, str] | None = None,
    *,
    connect: Callable[..., Any] | None = None,
) -> SalesMartDataFingerprint:
    """Read the development seed version and all canonical Sales Mart rows.

    The query account is the same read-only ``chatbi_app`` identity used by both
    expected SQL and generated SQL. Only counts, date bounds, and a hash leave
    this function; row values and connection details are never included in a
    report.
    """

    values = os.environ if environ is None else environ
    host = _required(values, "POSTGRES_HOST")
    database = _required(values, "POSTGRES_DB")
    user = _required(values, "POSTGRES_APP_USER")
    password = _required(values, "POSTGRES_APP_PASSWORD")
    if database != "chatbi_mvp":
        raise SalesMartFingerprintError("黄金评测必须连接日常开发数据库 chatbi_mvp")
    if user != "chatbi_app":
        raise SalesMartFingerprintError(
            "Sales Mart 数据指纹必须使用 chatbi_app 只读账号"
        )
    try:
        port = int(_required(values, "POSTGRES_PORT"))
    except ValueError:
        raise SalesMartFingerprintError("POSTGRES_PORT 配置无效") from None
    if not 1 <= port <= 65535:
        raise SalesMartFingerprintError("POSTGRES_PORT 配置无效")

    connector = psycopg.connect if connect is None else connect
    digest = hashlib.sha256()
    table_counts: dict[str, int] = {}
    seed_version: str | None = None
    minimum_date: str | None = None
    maximum_date: str | None = None
    try:
        with (
            connector(
                host=host,
                port=port,
                dbname=database,
                user=user,
                password=password,
                connect_timeout=5,
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cursor.execute("SELECT current_user, current_database()")
            identity = cursor.fetchone()
            if identity != ("chatbi_app", "chatbi_mvp"):
                raise SalesMartFingerprintError(
                    "评测数据库身份与 chatbi_mvp / chatbi_app 不匹配"
                )

            cursor.execute(
                "SELECT seed_version FROM mart_sales.dev_seed_metadata WHERE singleton"
            )
            seed_row = cursor.fetchone()
            if seed_row is None or not isinstance(seed_row[0], str):
                raise SalesMartFingerprintError(
                    "开发 Seed 版本不存在；请先初始化 chatbi_mvp"
                )
            seed_version = seed_row[0]

            for table_name, primary_key in _SALES_MART_TABLES:
                order_by = ", ".join(f'"{column}"' for column in primary_key)
                cursor.execute(
                    f'SELECT * FROM mart_sales."{table_name}" ORDER BY {order_by}'
                )
                rows = cursor.fetchall()
                description = cursor.description
                if description is None:
                    raise SalesMartFingerprintError("Sales Mart 表未返回字段信息")
                column_names = tuple(column.name for column in description)
                table_counts[table_name] = len(rows)
                _update_hash(digest, table_name, column_names, rows)

                if table_name == "dim_date" and rows:
                    full_date_index = column_names.index("full_date")
                    dates = [row[full_date_index].isoformat() for row in rows]
                    minimum_date, maximum_date = min(dates), max(dates)

        if not table_counts.get("fct_sales_order_line"):
            raise SalesMartFingerprintError(
                "Sales Mart 开发 Seed 中没有销售明细，无法生成评测数据指纹"
            )
        if seed_version is None:
            raise SalesMartFingerprintError("Sales Mart 开发 Seed 版本无法读取")
    except SalesMartFingerprintError:
        raise
    except Exception as error:
        raise SalesMartFingerprintError(
            "无法读取 chatbi_mvp 的 Sales Mart 数据指纹"
        ) from error

    return SalesMartDataFingerprint(
        seed_version=seed_version,
        data_summary={
            "table_counts": dict(sorted(table_counts.items())),
            "total_rows": sum(table_counts.values()),
            "date_range": {
                "start": minimum_date,
                "end": maximum_date,
            },
        },
        data_hash=digest.hexdigest(),
        hash_algorithm=SALES_MART_DATA_HASH_ALGORITHM,
    )


def _update_hash(
    digest: Any,
    table_name: str,
    column_names: tuple[str, ...],
    rows: list[tuple[object, ...]],
) -> None:
    digest.update(table_name.encode("utf-8"))
    digest.update(b"\0")
    digest.update(
        json.dumps(
            column_names,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    digest.update(b"\n")
    for row in rows:
        canonical_row = [_canonical_value(value) for value in row]
        encoded = json.dumps(
            canonical_row,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest.update(encoded)
        digest.update(b"\n")
    digest.update(f"rows={len(rows)}\n".encode("ascii"))


def _required(values: Mapping[str, str], key: str) -> str:
    value = values.get(key, "").strip()
    if not value:
        raise SalesMartFingerprintError(f"缺少 {key} 配置")
    return value
