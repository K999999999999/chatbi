"""验证 Schema Relationship 资源的物理约束和人工语义关系。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RELATIONSHIPS_PATH = ROOT / "resources" / "schema" / "relationships.json"
TABLES_PATH = ROOT / "resources" / "schema" / "tables.json"
COLUMNS_PATH = ROOT / "resources" / "schema" / "columns.json"

EXPECTED_RESOURCE_KEYS = {
    "schema_version",
    "primary_keys",
    "unique_constraints",
    "foreign_keys",
    "semantic_relationships",
}
EXPECTED_PRIMARY_KEYS = [
    {"table_name": "dim_customers", "column_names": ["customer_id"]},
    {"table_name": "dim_products", "column_names": ["product_id"]},
    {"table_name": "sales_orders", "column_names": ["order_id"]},
    {
        "table_name": "exchange_rates",
        "column_names": ["rate_date", "currency"],
    },
    {"table_name": "finance_expenses", "column_names": ["expense_id"]},
]
EXPECTED_UNIQUE_CONSTRAINTS = [
    {"table_name": "sales_orders", "column_names": ["order_no"]},
]
EXPECTED_FOREIGN_KEYS = [
    {
        "table_name": "sales_orders",
        "column_names": ["customer_id"],
        "referenced_table": "dim_customers",
        "referenced_column_names": ["customer_id"],
    },
    {
        "table_name": "sales_orders",
        "column_names": ["product_id"],
        "referenced_table": "dim_products",
        "referenced_column_names": ["product_id"],
    },
]
EXPECTED_SEMANTIC_RELATIONSHIPS = [
    {
        "relationship_id": "sales_orders_exchange_rates_by_order_date_currency",
        "source_table": "sales_orders",
        "source_columns": ["order_date", "currency"],
        "target_table": "exchange_rates",
        "target_columns": ["rate_date", "currency"],
        "cardinality": "many_to_one",
        "description": "销售订单按订单日期和交易币种匹配汇率。",
    }
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate() -> list[str]:
    resource = read_json(RELATIONSHIPS_PATH)
    tables = read_json(TABLES_PATH)
    columns = read_json(COLUMNS_PATH)
    errors: list[str] = []

    if not isinstance(resource, dict) or set(resource) != EXPECTED_RESOURCE_KEYS:
        errors.append("relationships.json top-level schema is invalid")
        return errors
    if resource.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    if not isinstance(tables, list) or not isinstance(columns, list):
        errors.append("tables.json and columns.json must be arrays")
        return errors
    table_names = {item.get("table_name") for item in tables if isinstance(item, dict)}
    catalog_fields = {
        (item.get("table_name"), item.get("column_name"))
        for item in columns
        if isinstance(item, dict)
    }

    if resource["primary_keys"] != EXPECTED_PRIMARY_KEYS:
        errors.append("primary_keys do not match the Course Baseline PostgreSQL facts")
    if resource["unique_constraints"] != EXPECTED_UNIQUE_CONSTRAINTS:
        errors.append("unique_constraints do not match the Course Baseline PostgreSQL facts")
    if resource["foreign_keys"] != EXPECTED_FOREIGN_KEYS:
        errors.append("foreign_keys do not match the Course Baseline PostgreSQL facts")
    if resource["semantic_relationships"] != EXPECTED_SEMANTIC_RELATIONSHIPS:
        errors.append("semantic_relationships do not match the maintained business fact")

    for relationship in resource["semantic_relationships"]:
        if not isinstance(relationship, dict):
            continue
        if relationship.get("source_table") not in table_names:
            errors.append("semantic relationship has an unknown source table")
        if relationship.get("target_table") not in table_names:
            errors.append("semantic relationship has an unknown target table")
        source_table = relationship.get("source_table")
        target_table = relationship.get("target_table")
        for column in relationship.get("source_columns", []):
            if (source_table, column) not in catalog_fields:
                errors.append(
                    f"semantic relationship source column is unknown: {source_table}.{column}"
                )
        for column in relationship.get("target_columns", []):
            if (target_table, column) not in catalog_fields:
                errors.append(
                    f"semantic relationship target column is unknown: {target_table}.{column}"
                )

    return errors


def main() -> int:
    try:
        errors = validate()
    except (OSError, json.JSONDecodeError, TypeError, AttributeError) as exc:
        print(f"validation_result = FAIL: {type(exc).__name__}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print("validation_result = FAIL")
        return 1

    print("schema_version = 1")
    print("primary_key_count = 5")
    print("unique_constraint_count = 1")
    print("foreign_key_count = 2")
    print("semantic_relationship_count = 1")
    print("finance_expenses_relationships = 0")
    print("validation_result = PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
