"""验证 Sales Domain V1 Semantic Layer 的机器可读契约。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


COMPLETED_FILTER = "fct_sales_order_line.order_status = 'completed'"
EXPECTED_METRIC_CODES = {
    "sales_quantity",
    "sales_revenue",
    "sales_cost",
    "gross_profit",
    "gross_margin",
}
LEGACY_TABLE_NAMES = {
    "sales_orders",
    "dim_customers",
    "dim_products",
    "exchange_rates",
    "finance_expenses",
}
class SalesSemanticResourcesTest(unittest.TestCase):
    """Sales Semantic Layer 只依赖当前 mart_sales Schema Metadata。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.resource_dir = ROOT / "resources" / "semantic" / "sales"
        cls.schema_dir = ROOT / "resources" / "schema"
        cls.metrics = cls._read_json("metrics.json")
        cls.tables = cls._read_schema_json("tables.json")
        cls.columns = cls._read_schema_json("columns.json")
        cls.relationships = cls._read_schema_json("relationships.json")

    @classmethod
    def _read_json(cls, filename: str) -> Any:
        return json.loads((cls.resource_dir / filename).read_text(encoding="utf-8"))

    @classmethod
    def _read_schema_json(cls, filename: str) -> Any:
        return json.loads((cls.schema_dir / filename).read_text(encoding="utf-8"))

    def test_resources_are_json_arrays(self) -> None:
        self.assertIsInstance(self.metrics, list)
        self.assertFalse((self.resource_dir / "dimensions.json").exists())

    def test_metric_contract_and_frozen_physical_mappings(self) -> None:
        required_fields = {
            "metric_code",
            "metric_name",
            "metric_type",
            "aliases",
            "business_definition",
            "expression",
            "filters",
            "depends_on",
            "default_time_column_identity",
            "unit",
        }
        self.assertEqual(
            EXPECTED_METRIC_CODES,
            {metric["metric_code"] for metric in self.metrics},
        )
        self.assertEqual(len(self.metrics), len(EXPECTED_METRIC_CODES))
        self.assertEqual(
            len(EXPECTED_METRIC_CODES),
            len({metric["metric_code"] for metric in self.metrics}),
        )

        table_names = {table["table_name"] for table in self.tables}
        column_names = {
            (column["table_name"], column["column_name"])
            for column in self.columns
        }
        for metric in self.metrics:
            self.assertTrue(required_fields.issubset(metric))
            self.assertEqual(COMPLETED_FILTER, metric["filters"][0])
            self.assertNotIn("default_time_dimension", metric)
            self.assertEqual(
                "mart_sales.fct_sales_order_line.completion_date_key",
                metric["default_time_column_identity"],
            )
            if metric["metric_type"] == "atomic":
                self.assertIn(metric["source_table"], table_names)
                for column in metric["source_columns"]:
                    self.assertIn((metric["source_table"], column), column_names)

        by_code = {metric["metric_code"]: metric for metric in self.metrics}
        for metric in self.metrics:
            for dependency in metric["depends_on"]:
                self.assertIn(dependency, by_code)

        self.assertEqual(
            "fct_sales_order_line",
            by_code["sales_revenue"]["source_table"],
        )
        self.assertEqual(
            ["net_sales_amount_cny"],
            by_code["sales_revenue"]["source_columns"],
        )
        self.assertEqual(
            ["sales_cost_amount_cny"],
            by_code["sales_cost"]["source_columns"],
        )
        self.assertEqual(
            "sales_revenue - sales_cost",
            by_code["gross_profit"]["expression"],
        )
        self.assertEqual(
            "gross_profit / sales_revenue",
            by_code["gross_margin"]["expression"],
        )
        self.assertEqual("sales_revenue = 0", by_code["gross_margin"]["null_if"])
        self.assertEqual(
            {"gross_margin"},
            {
                metric["metric_code"]
                for metric in self.metrics
                if "null_if" in metric
            },
        )

    def test_metric_dependencies_have_no_cycle(self) -> None:
        by_code = {metric["metric_code"]: metric for metric in self.metrics}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(metric_code: str) -> None:
            if metric_code in visiting:
                self.fail(f"metric dependency cycle includes {metric_code}")
            if metric_code in visited:
                return
            visiting.add(metric_code)
            for dependency in by_code[metric_code]["depends_on"]:
                visit(dependency)
            visiting.remove(metric_code)
            visited.add(metric_code)

        for metric_code in by_code:
            visit(metric_code)

    def test_business_dimension_fields_use_column_metadata(self) -> None:
        columns = {
            (column["table_name"], column["column_name"]): column
            for column in self.columns
        }
        required_fields = (
            ("dim_customer", "customer_region"),
            ("dim_customer", "customer_type"),
            ("dim_product", "product_line"),
            ("dim_sales_region", "sales_region_name"),
            ("fct_sales_order_line", "completion_date_key"),
        )
        for identity in required_fields:
            self.assertTrue(columns[identity]["column_name"])
            self.assertTrue(columns[identity]["description"])

        self.assertNotEqual(
            columns[("dim_customer", "customer_region")]["description"],
            columns[("dim_sales_region", "sales_region_name")]["description"],
        )

    def test_physical_relationships_are_not_duplicated_in_semantic_resources(self) -> None:
        self.assertIn("foreign_keys", self.relationships)
        self.assertNotIn("semantic_relationships", self.relationships)

    def test_legacy_tables_returns_and_expenses_are_absent(self) -> None:
        semantic_text = " ".join(self._strings(self.metrics))
        for table_name in LEGACY_TABLE_NAMES:
            self.assertNotIn(table_name, semantic_text)
        for forbidden_term in ("return", "expense", "退货", "费用"):
            self.assertNotIn(forbidden_term, semantic_text.casefold())

    @staticmethod
    def _strings(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [
                item
                for child in value
                for item in SalesSemanticResourcesTest._strings(child)
            ]
        if isinstance(value, dict):
            return [
                item
                for child in value.values()
                for item in SalesSemanticResourcesTest._strings(child)
            ]
        return []


if __name__ == "__main__":
    unittest.main(verbosity=2)
