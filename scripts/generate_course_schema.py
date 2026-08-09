"""从 Course Baseline V1 PostgreSQL 生成可读的物理 Schema 文本。"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "resources" / "schema" / "course_schema.txt"
TABLES_OUTPUT_PATH = ROOT / "resources" / "schema" / "tables.json"
COLUMNS_OUTPUT_PATH = ROOT / "resources" / "schema" / "columns.json"
RELATIONSHIPS_OUTPUT_PATH = ROOT / "resources" / "schema" / "relationships.json"
DATABASE_NAME = "chatbi_mvp"
APP_USER = "chatbi_app"
EXPECTED_TABLES = (
    "dim_customers",
    "dim_products",
    "sales_orders",
    "exchange_rates",
    "finance_expenses",
)

FIELD_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "dim_customers": {
        "customer_id": "客户ID",
        "customer_name": "客户名称",
        "customer_type": "客户类型",
        "industry": "客户所属行业",
        "country": "国家",
        "region": "客户所属区域",
    },
    "dim_products": {
        "product_id": "产品ID",
        "product_name": "产品名称",
        "product_line": "产品线",
        "category": "产品类别",
        "tech_route": "技术路线",
        "standard_cost": "标准/预算成本",
        "material_cost": "材料成本",
        "labor_cost": "人工成本",
    },
    "sales_orders": {
        "order_id": "订单ID",
        "order_no": "订单号",
        "customer_id": "客户ID",
        "product_id": "产品ID",
        "region": "销售区域",
        "order_date": "订单日期",
        "order_status": "订单状态",
        "quantity": "销售数量",
        "unit_price": "单位价格",
        "discount_amount": "折扣金额",
        "gross_amount": "含税总额",
        "net_amount": "不含税收入",
        "currency": "交易币种",
    },
    "exchange_rates": {
        "rate_date": "汇率日期",
        "currency": "交易币种",
        "rate_to_cny": "兑人民币汇率",
    },
    "finance_expenses": {
        "expense_id": "费用ID",
        "expense_date": "费用日期",
        "department": "费用归属部门",
        "rd_expense": "研发费用",
        "selling_expense": "销售费用",
        "admin_expense": "管理费用",
        "finance_expense": "财务费用",
        "marketing_expense": "市场费用",
        "logistics_expense": "物流费用",
        "warranty_expense": "质保费用",
    },
}

EXPECTED_PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "dim_customers": ("customer_id",),
    "dim_products": ("product_id",),
    "sales_orders": ("order_id",),
    "exchange_rates": ("rate_date", "currency"),
    "finance_expenses": ("expense_id",),
}

EXPECTED_UNIQUES = (("sales_orders", ("order_no",)),)
EXPECTED_FOREIGN_KEYS = (
    ("sales_orders", "customer_id", "dim_customers", "customer_id"),
    ("sales_orders", "product_id", "dim_products", "product_id"),
)

TABLE_DESCRIPTIONS = {
    "dim_customers": "客户主数据表，记录客户基本属性、类型、行业、国家和所属区域。",
    "dim_products": "产品主数据表，记录产品名称、产品线、类别、技术路线和成本字段。",
    "sales_orders": "销售订单表，记录订单标识、客户和产品关联、销售区域、日期、状态、数量、金额及币种。",
    "exchange_rates": "汇率表，记录交易日期、币种及兑人民币汇率。",
    "finance_expenses": "财务费用表，记录按日期和部门划分的各类费用。",
}


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
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
    password = env.get("POSTGRES_APP_PASSWORD")
    if not password:
        raise RuntimeError("POSTGRES_APP_PASSWORD is missing from .env")
    return {
        "host": "127.0.0.1",
        "port": 5433,
        "dbname": DATABASE_NAME,
        "user": APP_USER,
        "password": password,
        "connect_timeout": 10,
        "row_factory": dict_row,
    }


def read_metadata(conn: psycopg.Connection[Any]) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        )
        tables = [row["table_name"] for row in cur.fetchall()]

        cur.execute(
            """
            SELECT table_name, column_name, data_type,
                   character_maximum_length, numeric_precision, numeric_scale,
                   ordinal_position
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = ANY(%s)
            ORDER BY table_name, ordinal_position
            """,
            (list(EXPECTED_TABLES),),
        )
        columns = cur.fetchall()

        cur.execute(
            """
            SELECT rel.relname AS table_name,
                   con.conname AS constraint_name,
                   CASE con.contype
                       WHEN 'p' THEN 'PRIMARY KEY'
                       WHEN 'u' THEN 'UNIQUE'
                   END AS constraint_type,
                   att.attname AS column_name,
                   keys.ordinality AS ordinal_position
            FROM pg_constraint AS con
            JOIN pg_class AS rel ON rel.oid = con.conrelid
            JOIN pg_namespace AS nsp ON nsp.oid = rel.relnamespace
            JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS keys(attnum, ordinality)
              ON TRUE
            JOIN pg_attribute AS att
              ON att.attrelid = rel.oid
             AND att.attnum = keys.attnum
            WHERE nsp.nspname = 'public'
              AND rel.relname = ANY(%s)
              AND con.contype IN ('p', 'u')
            ORDER BY rel.relname, con.conname, keys.ordinality
            """,
            (list(EXPECTED_TABLES),),
        )
        key_constraints = cur.fetchall()

        cur.execute(
            """
            SELECT child_ns.nspname AS table_schema,
                   child.relname AS table_name,
                   child_col.attname AS column_name,
                   parent.relname AS referenced_table,
                   parent_col.attname AS referenced_column,
                   child_keys.ordinality
            FROM pg_constraint AS con
            JOIN pg_class AS child ON child.oid = con.conrelid
            JOIN pg_namespace AS child_ns ON child_ns.oid = child.relnamespace
            JOIN pg_class AS parent ON parent.oid = con.confrelid
            JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS child_keys(attnum, ordinality)
              ON TRUE
            JOIN LATERAL unnest(con.confkey) WITH ORDINALITY AS parent_keys(attnum, ordinality)
              ON parent_keys.ordinality = child_keys.ordinality
            JOIN pg_attribute AS child_col
              ON child_col.attrelid = child.oid
             AND child_col.attnum = child_keys.attnum
            JOIN pg_attribute AS parent_col
              ON parent_col.attrelid = parent.oid
             AND parent_col.attnum = parent_keys.attnum
            WHERE con.contype = 'f'
              AND child_ns.nspname = 'public'
              AND child.relname = ANY(%s)
            ORDER BY child.relname, child_keys.ordinality
            """,
            (list(EXPECTED_TABLES),),
        )
        foreign_keys = cur.fetchall()

    return {
        "tables": tables,
        "columns": columns,
        "key_constraints": key_constraints,
        "foreign_keys": foreign_keys,
    }


def grouped_constraint_columns(rows: list[dict[str, Any]], constraint_type: str) -> dict[str, tuple[str, ...]]:
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in rows:
        if row["constraint_type"] == constraint_type:
            grouped[(row["table_name"], row["constraint_name"])].append(row["column_name"])
    return {
        table_name: tuple(columns)
        for (table_name, _constraint_name), columns in grouped.items()
    }


def unique_constraints(rows: list[dict[str, Any]]) -> list[tuple[str, tuple[str, ...]]]:
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in rows:
        if row["constraint_type"] == "UNIQUE":
            grouped[(row["table_name"], row["constraint_name"])].append(row["column_name"])
    return sorted((table_name, tuple(columns)) for (table_name, _), columns in grouped.items())


def foreign_key_list(rows: list[dict[str, Any]]) -> list[tuple[str, str, str, str]]:
    return sorted(
        (
            row["table_name"],
            row["column_name"],
            row["referenced_table"],
            row["referenced_column"],
        )
        for row in rows
    )


def format_postgres_type(row: dict[str, Any]) -> str:
    if row["data_type"] == "character varying":
        length = row["character_maximum_length"]
        return f"VARCHAR({length})" if length else "VARCHAR"
    if row["data_type"] == "numeric":
        precision = row["numeric_precision"]
        scale = row["numeric_scale"]
        return f"DECIMAL({precision},{scale})" if precision is not None else "DECIMAL"
    return str(row["data_type"]).upper()


def validate_metadata(metadata: dict[str, Any]) -> None:
    errors: list[str] = []
    actual_tables = tuple(metadata["tables"])
    if len(actual_tables) != 5:
        errors.append(f"table_count={len(actual_tables)}")
    if set(actual_tables) != set(EXPECTED_TABLES):
        errors.append(f"tables={actual_tables}")

    columns_by_table: dict[str, list[str]] = defaultdict(list)
    for row in metadata["columns"]:
        columns_by_table[row["table_name"]].append(row["column_name"])
    if set(columns_by_table) != set(EXPECTED_TABLES):
        errors.append("column tables do not match expected tables")
    for table in EXPECTED_TABLES:
        expected_fields = tuple(FIELD_DESCRIPTIONS[table])
        if tuple(columns_by_table[table]) != expected_fields:
            errors.append(f"fields[{table}]={tuple(columns_by_table[table])}")

    actual_pks = grouped_constraint_columns(metadata["key_constraints"], "PRIMARY KEY")
    if actual_pks != EXPECTED_PRIMARY_KEYS:
        errors.append(f"primary_keys={actual_pks}")

    actual_uniques = unique_constraints(metadata["key_constraints"])
    if actual_uniques != list(EXPECTED_UNIQUES):
        errors.append(f"uniques={actual_uniques}")

    actual_fks = foreign_key_list(metadata["foreign_keys"])
    if actual_fks != sorted(EXPECTED_FOREIGN_KEYS):
        errors.append(f"foreign_keys={actual_fks}")

    rendered_fields = {
        (row["table_name"], row["column_name"])
        for row in metadata["columns"]
    }
    described_fields = {
        (table, column)
        for table, fields in FIELD_DESCRIPTIONS.items()
        for column in fields
    }
    if rendered_fields != described_fields:
        errors.append("schema descriptions contain fields absent from or missing in the database")

    if errors:
        raise RuntimeError("Schema validation failed: " + "; ".join(errors))


def render_schema(metadata: dict[str, Any]) -> str:
    columns_by_table: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in metadata["columns"]:
        columns_by_table[row["table_name"]].append(row)

    primary_keys = grouped_constraint_columns(metadata["key_constraints"], "PRIMARY KEY")
    unique_fields = {
        (table_name, column)
        for table_name, columns in unique_constraints(metadata["key_constraints"])
        for column in columns
    }
    foreign_keys = defaultdict(list)
    for row in metadata["foreign_keys"]:
        foreign_keys[(row["table_name"], row["column_name"])].append(
            (row["referenced_table"], row["referenced_column"])
        )

    lines = [
        "# Course Schema Baseline V1",
        "",
        "> 仅描述 PostgreSQL public Schema 的表、字段和约束。业务规则、指标公式和查询策略不属于本文件。",
        "",
    ]
    for table in EXPECTED_TABLES:
        lines.append(f"表：{table}")
        for row in columns_by_table[table]:
            column = row["column_name"]
            markers: list[str] = []
            if column in primary_keys[table]:
                markers.append("主键")
            if (table, column) in unique_fields:
                markers.append("唯一")
            marker_text = f" [{ '，'.join(markers) }]" if markers else ""
            lines.append(
                f"- {column} {format_postgres_type(row)}{marker_text}："
                f"{FIELD_DESCRIPTIONS[table][column]}"
            )
            for referenced_table, referenced_column in foreign_keys[(table, column)]:
                lines.append(f"  外键 → {referenced_table}.{referenced_column}")
        if len(primary_keys[table]) > 1:
            lines.append(f"联合主键：{' + '.join(primary_keys[table])}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_json_catalog(metadata: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, list[dict[str, Any]]]]:
    columns_by_table: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in metadata["columns"]:
        columns_by_table[row["table_name"]].append(row)

    primary_keys = grouped_constraint_columns(metadata["key_constraints"], "PRIMARY KEY")
    tables = [
        {"table_name": table, "description": TABLE_DESCRIPTIONS[table]}
        for table in EXPECTED_TABLES
    ]
    columns = [
        {
            "table_name": table,
            "column_name": row["column_name"],
            "data_type": format_postgres_type(row),
            "description": FIELD_DESCRIPTIONS[table][row["column_name"]],
        }
        for table in EXPECTED_TABLES
        for row in columns_by_table[table]
    ]
    relationships = {
        "primary_keys": [
            {"table_name": table, "column_names": list(primary_keys[table])}
            for table in EXPECTED_TABLES
        ],
        "foreign_keys": [
            {
                "table_name": table,
                "column_name": column,
                "referenced_table": referenced_table,
                "referenced_column": referenced_column,
            }
            for table, column, referenced_table, referenced_column in foreign_key_list(
                metadata["foreign_keys"]
            )
        ],
    }
    return tables, columns, relationships


def validate_json_catalog(
    metadata: dict[str, Any],
    tables: list[dict[str, str]],
    columns: list[dict[str, str]],
    relationships: dict[str, list[dict[str, Any]]],
) -> None:
    actual_fields = {
        (row["table_name"], row["column_name"])
        for row in metadata["columns"]
    }
    catalog_fields = {
        (row["table_name"], row["column_name"])
        for row in columns
    }
    if len(tables) != 5 or {row["table_name"] for row in tables} != set(EXPECTED_TABLES):
        raise RuntimeError("tables.json must contain exactly 5 database tables")
    if len(columns) != 40 or catalog_fields != actual_fields:
        raise RuntimeError("columns.json must contain exactly the database fields")
    if set(catalog_fields) != {
        (table, column)
        for table, fields in FIELD_DESCRIPTIONS.items()
        for column in fields
    }:
        raise RuntimeError("columns.json contains a field without a confirmed description")

    expected_primary_keys = [
        {"table_name": table, "column_names": list(EXPECTED_PRIMARY_KEYS[table])}
        for table in EXPECTED_TABLES
    ]
    if relationships["primary_keys"] != expected_primary_keys:
        raise RuntimeError("relationships.json primary_keys do not match PostgreSQL")
    expected_foreign_keys = [
        {
            "table_name": table,
            "column_name": column,
            "referenced_table": referenced_table,
            "referenced_column": referenced_column,
        }
        for table, column, referenced_table, referenced_column in sorted(EXPECTED_FOREIGN_KEYS)
    ]
    if relationships["foreign_keys"] != expected_foreign_keys:
        raise RuntimeError("relationships.json foreign_keys do not match PostgreSQL")


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    try:
        env = load_env(ROOT / ".env")
        with psycopg.connect(**connection_config(env)) as conn:
            metadata = read_metadata(conn)
        validate_metadata(metadata)
        content = render_schema(metadata)
        tables, columns, relationships = build_json_catalog(metadata)
        validate_json_catalog(metadata, tables, columns, relationships)
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(content, encoding="utf-8", newline="\n")
        write_json(TABLES_OUTPUT_PATH, tables)
        write_json(COLUMNS_OUTPUT_PATH, columns)
        write_json(RELATIONSHIPS_OUTPUT_PATH, relationships)
        print("table_count = 5")
        print("column_count = 40")
        print("relationship_count = 2")
        print("tables = " + ", ".join(EXPECTED_TABLES))
        print("primary_key_count = 5")
        print("foreign_key_count = 2")
        print("unique = sales_orders.order_no")
        print(f"output = {OUTPUT_PATH}")
        print("validation_result = PASS")
        return 0
    except (OSError, RuntimeError, psycopg.Error) as exc:
        print(f"validation_result = FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
