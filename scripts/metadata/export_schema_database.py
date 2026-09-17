"""Metadata Export 的 PostgreSQL 只读读取和 Canonical Schema 构建。"""

from collections.abc import Iterable
from dataclasses import replace
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .export_schema_models import (
    EXPECTED_TABLES,
    TARGET_SCHEMA,
    CanonicalSchema,
    ColumnMetadata,
    ConstraintMetadata,
    ForeignKeyMetadata,
    MetadataExportError,
    TableMetadata,
    UniqueIndexMetadata,
)


TABLES_QUERY = """
SELECT
    t.table_schema AS schema_name,
    t.table_name,
    t.table_type,
    obj_description(c.oid, 'pg_class') AS description
FROM information_schema.tables AS t
JOIN pg_catalog.pg_namespace AS n
  ON n.nspname = t.table_schema
JOIN pg_catalog.pg_class AS c
  ON c.relnamespace = n.oid
 AND c.relname = t.table_name
WHERE t.table_schema = %s
  AND t.table_type = 'BASE TABLE'
ORDER BY t.table_name
"""

COLUMNS_QUERY = """
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    a.attname AS column_name,
    a.attnum AS ordinal_position,
    pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
    NOT a.attnotnull AS nullable,
    pg_catalog.pg_get_expr(ad.adbin, ad.adrelid) AS default_value,
    pg_catalog.col_description(c.oid, a.attnum) AS description,
    a.attidentity AS identity_kind
FROM pg_catalog.pg_attribute AS a
JOIN pg_catalog.pg_class AS c
  ON c.oid = a.attrelid
JOIN pg_catalog.pg_namespace AS n
  ON n.oid = c.relnamespace
LEFT JOIN pg_catalog.pg_attrdef AS ad
  ON ad.adrelid = a.attrelid
 AND ad.adnum = a.attnum
WHERE n.nspname = %s
  AND c.relkind = 'r'
  AND a.attnum > 0
  AND NOT a.attisdropped
ORDER BY c.relname, a.attnum
"""

CONSTRAINTS_QUERY = """
SELECT
    c.contype,
    c.conname AS constraint_name,
    n.nspname AS schema_name,
    r.relname AS table_name,
    array_agg(a.attname ORDER BY key_columns.ordinality) AS column_names,
    referenced_n.nspname AS referenced_schema,
    referenced_r.relname AS referenced_table,
    array_agg(referenced_a.attname ORDER BY key_columns.ordinality)
        FILTER (WHERE referenced_a.attname IS NOT NULL)
        AS referenced_column_names
FROM pg_catalog.pg_constraint AS c
JOIN pg_catalog.pg_class AS r
  ON r.oid = c.conrelid
JOIN pg_catalog.pg_namespace AS n
  ON n.oid = r.relnamespace
JOIN LATERAL unnest(c.conkey) WITH ORDINALITY
    AS key_columns(attnum, ordinality)
  ON TRUE
JOIN pg_catalog.pg_attribute AS a
  ON a.attrelid = c.conrelid
 AND a.attnum = key_columns.attnum
LEFT JOIN pg_catalog.pg_class AS referenced_r
  ON referenced_r.oid = c.confrelid
LEFT JOIN pg_catalog.pg_namespace AS referenced_n
  ON referenced_n.oid = referenced_r.relnamespace
LEFT JOIN LATERAL unnest(c.confkey) WITH ORDINALITY
    AS referenced_key_columns(attnum, ordinality)
  ON referenced_key_columns.ordinality = key_columns.ordinality
LEFT JOIN pg_catalog.pg_attribute AS referenced_a
  ON referenced_a.attrelid = c.confrelid
 AND referenced_a.attnum = referenced_key_columns.attnum
WHERE n.nspname = %s
  AND c.contype IN ('p', 'u', 'f')
GROUP BY
    c.contype,
    c.conname,
    n.nspname,
    r.relname,
    referenced_n.nspname,
    referenced_r.relname
ORDER BY r.relname, c.contype, c.conname
"""

UNIQUE_INDEXES_QUERY = """
SELECT
    n.nspname AS schema_name,
    table_r.relname AS table_name,
    index_r.relname AS index_name,
    array_agg(a.attname ORDER BY index_columns.ordinality)
        FILTER (WHERE a.attname IS NOT NULL)
        AS column_names,
    pg_catalog.pg_get_expr(index_info.indpred, index_info.indrelid) AS predicate
FROM pg_catalog.pg_index AS index_info
JOIN pg_catalog.pg_class AS table_r
  ON table_r.oid = index_info.indrelid
JOIN pg_catalog.pg_namespace AS n
  ON n.oid = table_r.relnamespace
JOIN pg_catalog.pg_class AS index_r
  ON index_r.oid = index_info.indexrelid
LEFT JOIN pg_catalog.pg_constraint AS constraint_info
  ON constraint_info.conindid = index_info.indexrelid
JOIN LATERAL unnest(index_info.indkey) WITH ORDINALITY
    AS index_columns(attnum, ordinality)
  ON TRUE
LEFT JOIN pg_catalog.pg_attribute AS a
  ON a.attrelid = index_info.indrelid
 AND a.attnum = index_columns.attnum
WHERE n.nspname = %s
  AND index_info.indisunique
  AND constraint_info.oid IS NULL
GROUP BY
    n.nspname,
    table_r.relname,
    index_r.relname,
    index_info.indpred,
    index_info.indrelid
ORDER BY table_r.relname, index_r.relname
"""


def _as_tuple(values: Iterable[str] | None) -> tuple[str, ...]:
    return tuple(str(value) for value in (values or ()))


def _constraint_sort_key(item: ConstraintMetadata) -> tuple[Any, ...]:
    return (item.table_name, item.column_names, item.constraint_name)


def _foreign_key_sort_key(item: ForeignKeyMetadata) -> tuple[Any, ...]:
    return (
        item.table_name,
        item.column_names,
        item.referenced_schema,
        item.referenced_table,
        item.referenced_column_names,
        item.constraint_name,
    )


def _unique_index_sort_key(item: UniqueIndexMetadata) -> tuple[Any, ...]:
    return (item.table_name, item.index_name, item.column_names)


def _fetch_tables(cur: Any, schema_name: str) -> tuple[TableMetadata, ...]:
    cur.execute(TABLES_QUERY, (schema_name,))
    tables = tuple(
        TableMetadata(
            schema_name=str(row["schema_name"]),
            table_name=str(row["table_name"]),
            table_type=str(row["table_type"]),
            description=(
                str(row["description"])
                if row["description"] is not None
                else None
            ),
        )
        for row in cur.fetchall()
    )
    actual_tables = {table.table_name for table in tables}
    if actual_tables != EXPECTED_TABLES:
        missing = sorted(EXPECTED_TABLES - actual_tables)
        unexpected = sorted(actual_tables - EXPECTED_TABLES)
        raise MetadataExportError(
            "mart_sales 表集合不符合当前 V1 契约："
            f"missing={missing}, unexpected={unexpected}"
        )
    return tables


def _fetch_columns(cur: Any, schema_name: str) -> tuple[ColumnMetadata, ...]:
    cur.execute(COLUMNS_QUERY, (schema_name,))
    columns: list[ColumnMetadata] = []
    for row in cur.fetchall():
        identity_kind = str(row["identity_kind"] or "")
        columns.append(
            ColumnMetadata(
                schema_name=str(row["schema_name"]),
                table_name=str(row["table_name"]),
                column_name=str(row["column_name"]),
                ordinal_position=int(row["ordinal_position"]),
                data_type=str(row["data_type"]),
                nullable=bool(row["nullable"]),
                default=(
                    str(row["default_value"])
                    if row["default_value"] is not None
                    else None
                ),
                description=(
                    str(row["description"])
                    if row["description"] is not None
                    else None
                ),
                is_identity=bool(identity_kind),
                identity_generation={
                    "a": "ALWAYS",
                    "d": "BY DEFAULT",
                }.get(identity_kind),
            )
        )
    return tuple(columns)


def _fetch_constraints(
    cur: Any,
    schema_name: str,
) -> tuple[
    tuple[ConstraintMetadata, ...],
    tuple[ConstraintMetadata, ...],
    tuple[ForeignKeyMetadata, ...],
]:
    cur.execute(CONSTRAINTS_QUERY, (schema_name,))
    primary_keys: list[ConstraintMetadata] = []
    unique_constraints: list[ConstraintMetadata] = []
    foreign_keys: list[ForeignKeyMetadata] = []
    for row in cur.fetchall():
        contype = str(row["contype"])
        if contype in {"p", "u"}:
            constraint = ConstraintMetadata(
                schema_name=str(row["schema_name"]),
                table_name=str(row["table_name"]),
                column_names=_as_tuple(row["column_names"]),
                constraint_name=str(row["constraint_name"]),
            )
            if contype == "p":
                primary_keys.append(constraint)
            else:
                unique_constraints.append(constraint)
            continue

        referenced_schema = row["referenced_schema"]
        referenced_table = row["referenced_table"]
        referenced_column_names = row["referenced_column_names"]
        if (
            referenced_schema is None
            or referenced_table is None
            or referenced_column_names is None
        ):
            raise MetadataExportError(
                f"外键约束缺少引用目标：{row['constraint_name']}"
            )
        foreign_keys.append(
            ForeignKeyMetadata(
                schema_name=str(row["schema_name"]),
                table_name=str(row["table_name"]),
                column_names=_as_tuple(row["column_names"]),
                referenced_schema=str(referenced_schema),
                referenced_table=str(referenced_table),
                referenced_column_names=_as_tuple(referenced_column_names),
                constraint_name=str(row["constraint_name"]),
            )
        )

    return (
        tuple(sorted(primary_keys, key=_constraint_sort_key)),
        tuple(sorted(unique_constraints, key=_constraint_sort_key)),
        tuple(sorted(foreign_keys, key=_foreign_key_sort_key)),
    )


def _fetch_unique_indexes(
    cur: Any,
    schema_name: str,
) -> tuple[UniqueIndexMetadata, ...]:
    cur.execute(UNIQUE_INDEXES_QUERY, (schema_name,))
    indexes = [
        UniqueIndexMetadata(
            schema_name=str(row["schema_name"]),
            table_name=str(row["table_name"]),
            index_name=str(row["index_name"]),
            column_names=_as_tuple(row["column_names"]),
            predicate=(
                str(row["predicate"]) if row["predicate"] is not None else None
            ),
        )
        for row in cur.fetchall()
    ]
    return tuple(sorted(indexes, key=_unique_index_sort_key))


def extract_schema(
    conn: psycopg.Connection[Any],
    schema_name: str = TARGET_SCHEMA,
) -> CanonicalSchema:
    """在一个连接中提取 mart_sales 并构造 Canonical Schema Model。"""

    if schema_name != TARGET_SCHEMA:
        raise MetadataExportError(f"只允许导出 {TARGET_SCHEMA} Schema")

    with conn.cursor(row_factory=dict_row) as cur:
        tables = _fetch_tables(cur, schema_name)
        columns = _fetch_columns(cur, schema_name)
        primary_keys, unique_constraints, foreign_keys = _fetch_constraints(
            cur, schema_name
        )
        unique_indexes = _fetch_unique_indexes(cur, schema_name)

    table_names = {table.table_name for table in tables}
    invalid_columns = sorted(
        {
            column.table_name
            for column in columns
            if column.table_name not in table_names
        }
    )
    if invalid_columns:
        raise MetadataExportError(f"字段属于未导出的表：{invalid_columns}")

    primary_key_columns = {
        (item.table_name, column_name)
        for item in primary_keys
        for column_name in item.column_names
    }
    foreign_key_columns = {
        (item.table_name, column_name)
        for item in foreign_keys
        for column_name in item.column_names
    }
    columns = tuple(
        replace(
            column,
            is_primary_key=(column.table_name, column.column_name)
            in primary_key_columns,
            is_foreign_key=(column.table_name, column.column_name)
            in foreign_key_columns,
        )
        for column in columns
    )
    return CanonicalSchema(
        schema_name=schema_name,
        tables=tuple(sorted(tables, key=lambda item: item.table_name)),
        columns=tuple(
            sorted(columns, key=lambda item: (item.table_name, item.ordinal_position))
        ),
        primary_keys=primary_keys,
        unique_constraints=unique_constraints,
        foreign_keys=foreign_keys,
        unique_indexes=unique_indexes,
    )
