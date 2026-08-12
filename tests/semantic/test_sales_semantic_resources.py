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
EXPECTED_DIMENSION_CODES = {
    "completion_date",
    "order_date",
    "confirmation_date",
    "customer",
    "customer_type",
    "industry",
    "country",
    "customer_region",
    "product",
    "product_line",
    "product_category",
    "technology_route",
    "sales_region",
    "transaction_currency",
    "order_no",
}
TECHNICAL_DIMENSION_FIELDS = {
    "sales_order_line_key",
    "customer_key",
    "product_key",
    "sales_region_key",
    "currency_key",
    "valid_from",
    "valid_to",
    "is_current",
    "source_system",
    "source_updated_at",
    "loaded_at",
}
LEGACY_TABLE_NAMES = {
    "sales_orders",
    "dim_customers",
    "dim_products",
    "exchange_rates",
    "finance_expenses",
}
FORBIDDEN_SEMANTIC_KEYS = {
    "join",
    "joins",
    "join_path",
    "join_paths",
    "foreign_keys",
    "relationships",
}


class SalesSemanticResourcesTest(unittest.TestCase):
    """Sales Semantic Layer 只依赖当前 mart_sales Schema Metadata。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.resource_dir = ROOT / "resources" / "semantic" / "sales"
        cls.schema_dir = ROOT / "resources" / "schema"
        cls.metrics = cls._read_json("metrics.json")
        cls.dimensions = cls._read_json("dimensions.json")
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
        self.assertIsInstance(self.dimensions, list)

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
            "default_time_dimension",
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
            self.assertEqual("completion_date", metric["default_time_dimension"])
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

    def test_dimension_contract_and_physical_mappings(self) -> None:
        required_fields = {
            "dimension_code",
            "dimension_name",
            "aliases",
            "business_definition",
            "dimension_type",
            "source_table",
            "source_column",
        }
        self.assertEqual(
            EXPECTED_DIMENSION_CODES,
            {dimension["dimension_code"] for dimension in self.dimensions},
        )
        self.assertEqual(len(self.dimensions), len(EXPECTED_DIMENSION_CODES))
        self.assertEqual(
            len(EXPECTED_DIMENSION_CODES),
            len({dimension["dimension_code"] for dimension in self.dimensions}),
        )

        table_names = {table["table_name"] for table in self.tables}
        column_names = {
            (column["table_name"], column["column_name"])
            for column in self.columns
        }
        for dimension in self.dimensions:
            self.assertTrue(required_fields.issubset(dimension))
            self.assertIn(dimension["source_table"], table_names)
            self.assertIn(
                (dimension["source_table"], dimension["source_column"]),
                column_names,
            )

        time_dimensions = {
            dimension["dimension_code"]: dimension
            for dimension in self.dimensions
            if dimension["dimension_type"] == "time"
        }
        self.assertEqual(
            {"completion_date", "order_date", "confirmation_date"},
            set(time_dimensions),
        )
        self.assertEqual(
            {"completion_date"},
            {
                code
                for code, dimension in time_dimensions.items()
                if dimension["is_default_business_time"]
            },
        )
        for dimension in time_dimensions.values():
            self.assertEqual("dim_date", dimension["date_dimension_table"])
            self.assertEqual("date_key", dimension["date_key_column"])
            self.assertEqual("full_date", dimension["source_column"])

    def test_business_boundaries_are_not_ambiguous_or_technical(self) -> None:
        by_code = {dimension["dimension_code"]: dimension for dimension in self.dimensions}
        customer_region_aliases = set(by_code["customer_region"]["aliases"])
        sales_region_aliases = set(by_code["sales_region"]["aliases"])
        self.assertTrue(customer_region_aliases.isdisjoint(sales_region_aliases))
        self.assertNotIn("区域", customer_region_aliases | sales_region_aliases)

        exposed_fields = {
            value
            for dimension in self.dimensions
            for value in (dimension["dimension_code"], dimension["source_column"])
        }
        self.assertTrue(TECHNICAL_DIMENSION_FIELDS.isdisjoint(exposed_fields))
        self.assertNotIn("hierarchy", " ".join(self._strings(self.dimensions)).lower())

    def test_physical_relationships_are_not_duplicated_in_semantic_resources(self) -> None:
        self.assertIn("foreign_keys", self.relationships)
        self.assertNotIn("semantic_relationships", self.relationships)
        for dimension in self.dimensions:
            self.assertTrue(FORBIDDEN_SEMANTIC_KEYS.isdisjoint(dimension))

    def test_legacy_tables_returns_and_expenses_are_absent(self) -> None:
        semantic_text = " ".join(self._strings(self.metrics + self.dimensions))
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
