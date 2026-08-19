"""从 PostgreSQL mart_sales 结构生成当前 Sales Mart V1 Schema Metadata。

本模块只读取 PostgreSQL 系统目录，并遵循一次提取、多份投影：

    PostgreSQL
        ↓
    CanonicalSchema（统一结构模型）
        ↓
    tables.json / columns.json / relationships.json

它不读取 DOMAIN_SPEC、ANALYTICAL_MODEL 或 Semantic Layer（语义层）来
补充业务描述；表和字段描述只能来自 PostgreSQL COMMENT（注释）。
数据库连接期间只执行 SELECT，不创建、修改或删除数据库对象及数据。
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[2]
TARGET_SCHEMA = "mart_sales"
EXPECTED_TABLES = frozenset(
    {
        "dim_date",
        "dim_customer",
        "dim_product",
        "dim_sales_region",
        "dim_currency",
        "fct_exchange_rate_daily",
        "fct_sales_order_line",
    }
)
OUTPUT_FILES = {
    "tables": "tables.json",
    "columns": "columns.json",
    "relationships": "relationships.json",
}
DEFAULT_OUTPUT_DIR = ROOT / "src" / "poc" / "structure" / "generated"


class MetadataExportError(RuntimeError):
    """Schema Metadata（结构元数据）无法满足当前导出契约。"""


@dataclass(frozen=True)
class TableMetadata:
    schema_name: str
    table_name: str
    table_type: str
    description: str | None


@dataclass(frozen=True)
class ColumnMetadata:
    schema_name: str
    table_name: str
    column_name: str
    ordinal_position: int
    data_type: str
    nullable: bool
    default: str | None
    description: str | None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    is_identity: bool = False
    identity_generation: str | None = None


@dataclass(frozen=True)
class ConstraintMetadata:
    schema_name: str
    table_name: str
    column_names: tuple[str, ...]
    constraint_name: str


@dataclass(frozen=True)
class ForeignKeyMetadata:
    schema_name: str
    table_name: str
    column_names: tuple[str, ...]
    referenced_schema: str
    referenced_table: str
    referenced_column_names: tuple[str, ...]
    constraint_name: str


@dataclass(frozen=True)
class UniqueIndexMetadata:
    schema_name: str
    table_name: str
    index_name: str
    column_names: tuple[str, ...]
    predicate: str | None


@dataclass(frozen=True)
class CanonicalSchema:
    """一次 PostgreSQL 扫描形成的统一结构模型。"""

    schema_name: str
    tables: tuple[TableMetadata, ...]
    columns: tuple[ColumnMetadata, ...]
    primary_keys: tuple[ConstraintMetadata, ...]
    unique_constraints: tuple[ConstraintMetadata, ...]
    foreign_keys: tuple[ForeignKeyMetadata, ...]
    unique_indexes: tuple[UniqueIndexMetadata, ...]


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


def load_env(path: Path) -> dict[str, str]:
    """读取本地连接配置，不输出任何 Secret（敏感信息）。"""

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def connection_config(env: dict[str, str]) -> dict[str, Any]:
    """构造只用于本地元数据读取的 PostgreSQL 连接配置。"""

    required = ("POSTGRES_MIGRATOR_USER", "POSTGRES_MIGRATOR_PASSWORD")
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise MetadataExportError(f".env 缺少必要配置：{', '.join(missing)}")
    return {
        "host": env.get("POSTGRES_HOST", "127.0.0.1"),
        "port": int(env.get("POSTGRES_PORT", "5432")),
        "dbname": env.get("POSTGRES_DB", "chatbi_mvp"),
        "user": env["POSTGRES_MIGRATOR_USER"],
        "password": env["POSTGRES_MIGRATOR_PASSWORD"],
        "connect_timeout": 10,
    }


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


def project_tables(model: CanonicalSchema) -> list[dict[str, Any]]:
    """将统一模型投影为 tables.json。"""

    return [
        {
            "schema_name": table.schema_name,
            "table_name": table.table_name,
            "table_type": table.table_type,
            "description": table.description,
        }
        for table in model.tables
    ]


def project_columns(model: CanonicalSchema) -> list[dict[str, Any]]:
    """将统一模型投影为 columns.json。"""

    return [
        {
            "schema_name": column.schema_name,
            "table_name": column.table_name,
            "column_name": column.column_name,
            "ordinal_position": column.ordinal_position,
            "data_type": column.data_type,
            "nullable": column.nullable,
            "default": column.default,
            "description": column.description,
            "is_primary_key": column.is_primary_key,
            "is_foreign_key": column.is_foreign_key,
            "is_identity": column.is_identity,
            "identity_generation": column.identity_generation,
        }
        for column in model.columns
    ]


def project_relationships(model: CanonicalSchema) -> dict[str, Any]:
    """将统一模型投影为物理 relationships.json，不写入语义关系。"""

    return {
        "schema_version": 1,
        "primary_keys": [
            {
                "schema_name": item.schema_name,
                "table_name": item.table_name,
                "column_names": list(item.column_names),
            }
            for item in model.primary_keys
        ],
        "unique_constraints": [
            {
                "schema_name": item.schema_name,
                "table_name": item.table_name,
                "column_names": list(item.column_names),
            }
            for item in model.unique_constraints
        ],
        "foreign_keys": [
            {
                "schema_name": item.schema_name,
                "table_name": item.table_name,
                "column_names": list(item.column_names),
                "referenced_schema": item.referenced_schema,
                "referenced_table": item.referenced_table,
                "referenced_column_names": list(item.referenced_column_names),
            }
            for item in model.foreign_keys
        ],
        "unique_indexes": [
            {
                "schema_name": item.schema_name,
                "table_name": item.table_name,
                "index_name": item.index_name,
                "column_names": list(item.column_names),
                "predicate": item.predicate,
            }
            for item in model.unique_indexes
        ],
    }


def project_outputs(model: CanonicalSchema) -> dict[str, Any]:
    """从同一个 Canonical Schema Model 生成三份输出对象。"""

    return {
        "tables": project_tables(model),
        "columns": project_columns(model),
        "relationships": project_relationships(model),
    }


def render_json(value: Any) -> str:
    """以固定格式序列化 JSON，保证重复导出内容稳定。"""

    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def write_outputs(outputs: dict[str, Any], output_dir: Path) -> None:
    """写入三份正式 Schema Metadata（结构元数据）资源。"""

    output_dir.mkdir(parents=True, exist_ok=True)
    for key, filename in OUTPUT_FILES.items():
        path = output_dir / filename
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(render_json(outputs[key]))


def export_schema(
    env_file: Path = ROOT / ".env",
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> CanonicalSchema:
    """连接一次 PostgreSQL，提取并写出当前 mart_sales Metadata。"""

    env = load_env(env_file)
    with psycopg.connect(**connection_config(env)) as conn:
        model = extract_schema(conn)
    write_outputs(project_outputs(model), output_dir)
    return model


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export the current mart_sales PostgreSQL schema metadata"
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=ROOT / ".env",
        help="path to the local PostgreSQL environment file",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="directory for tables.json, columns.json, and relationships.json",
    )
    args = parser.parse_args()

    try:
        model = export_schema(args.env_file, args.output_dir)
    except (OSError, psycopg.Error, MetadataExportError, ValueError) as exc:
        print(f"metadata_export_result = FAIL: {type(exc).__name__}")
        return 1

    print(f"schema = {model.schema_name}")
    print(f"table_count = {len(model.tables)}")
    print(f"column_count = {len(model.columns)}")
    print(f"primary_key_count = {len(model.primary_keys)}")
    print(f"unique_constraint_count = {len(model.unique_constraints)}")
    print(f"foreign_key_count = {len(model.foreign_keys)}")
    print(f"unique_index_count = {len(model.unique_indexes)}")
    print("metadata_export_result = PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
