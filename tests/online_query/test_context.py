"""静态结构与指标上下文加载测试。"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.online_query.context import ContextLoadError, load_query_context


class ContextTest(unittest.TestCase):
    def setUp(self) -> None:
        load_query_context.cache_clear()

    def test_loads_four_files_with_column_value_examples_and_caches_context(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            structure_dir, metrics_path = self._write_valid_context(root)

            first = load_query_context(structure_dir, metrics_path)
            second = load_query_context(structure_dir, metrics_path)

            self.assertIs(first, second)
            self.assertEqual(
                first.allowed_tables,
                frozenset({"mart_sales.fct_sales_order_line"}),
            )
            self.assertEqual(
                first.allowed_columns["mart_sales.fct_sales_order_line"],
                frozenset(
                    {"order_id", "net_sales_amount_cny", "order_status"}
                ),
            )
            self.assertIn("relationships", first.prompt_context)
            self.assertIn("value_examples", first.prompt_context)
            self.assertNotIn("column_values", first.prompt_context)
            self.assertIn("人民币净销售额", first.prompt_context)

    def test_missing_file_raises_controlled_error(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            structure_dir, metrics_path = self._write_valid_context(root)
            (structure_dir / "relationships.json").unlink()

            with self.assertRaisesRegex(ContextLoadError, "relationships"):
                load_query_context(structure_dir, metrics_path)

    def test_invalid_json_raises_controlled_error(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            structure_dir, metrics_path = self._write_valid_context(root)
            (structure_dir / "columns.json").write_text("{", encoding="utf-8")

            with self.assertRaisesRegex(ContextLoadError, "columns"):
                load_query_context(structure_dir, metrics_path)

    def test_empty_required_content_raises_controlled_error(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            structure_dir, metrics_path = self._write_valid_context(root)
            metrics_path.write_text("[]", encoding="utf-8")

            with self.assertRaisesRegex(ContextLoadError, "metrics"):
                load_query_context(structure_dir, metrics_path)

    def test_non_array_content_raises_controlled_error(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            structure_dir, metrics_path = self._write_valid_context(root)
            (structure_dir / "tables.json").write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(ContextLoadError, "tables"):
                load_query_context(structure_dir, metrics_path)

    def test_invalid_column_value_examples_raise_controlled_error(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            structure_dir, metrics_path = self._write_valid_context(root)
            columns_path = structure_dir / "columns.json"
            columns = json.loads(columns_path.read_text(encoding="utf-8"))
            columns[2]["value_examples"] = ["completed", "completed"]
            columns_path.write_text(json.dumps(columns), encoding="utf-8")

            with self.assertRaisesRegex(ContextLoadError, "value_examples"):
                load_query_context(structure_dir, metrics_path)

    @staticmethod
    def _write_valid_context(root: Path) -> tuple[Path, Path]:
        structure_dir = root / "structure"
        structure_dir.mkdir()
        semantic_dir = root / "semantic"
        semantic_dir.mkdir()
        metrics_path = semantic_dir / "metrics.json"

        resources = {
            "tables.json": [
                {
                    "schema_name": "mart_sales",
                    "table_name": "fct_sales_order_line",
                    "description": "销售订单明细",
                }
            ],
            "columns.json": [
                {
                    "schema_name": "mart_sales",
                    "table_name": "fct_sales_order_line",
                    "column_name": "order_id",
                },
                {
                    "schema_name": "mart_sales",
                    "table_name": "fct_sales_order_line",
                    "column_name": "net_sales_amount_cny",
                },
                {
                    "schema_name": "mart_sales",
                    "table_name": "fct_sales_order_line",
                    "column_name": "order_status",
                    "value_examples": ["completed"],
                },
            ],
            "relationships.json": [
                {
                    "relationship_type": "primary_key",
                    "schema_name": "mart_sales",
                    "table_name": "fct_sales_order_line",
                    "column_names": ["order_id"],
                    "constraint_name": "fct_sales_order_line_pkey",
                }
            ],
        }
        for filename, records in resources.items():
            (structure_dir / filename).write_text(
                json.dumps(records, ensure_ascii=False),
                encoding="utf-8",
            )
        metrics_path.write_text(
            json.dumps(
                [
                    {
                        "name": "人民币净销售额",
                        "formula": "SUM(f.net_sales_amount_cny)",
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return structure_dir, metrics_path

    def test_builds_direct_join_constraints_from_fk_pk_facts(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            structure_dir, metrics_path = self._write_valid_context(root)

            tables_path = structure_dir / "tables.json"
            tables = json.loads(tables_path.read_text(encoding="utf-8"))
            tables.append(
                {
                    "schema_name": "mart_sales",
                    "table_name": "dim_customer",
                    "description": "客户维度",
                }
            )
            tables_path.write_text(
                json.dumps(tables, ensure_ascii=False),
                encoding="utf-8",
            )

            columns_path = structure_dir / "columns.json"
            columns = json.loads(columns_path.read_text(encoding="utf-8"))
            columns.extend(
                [
                    {
                        "schema_name": "mart_sales",
                        "table_name": "fct_sales_order_line",
                        "column_name": "customer_key",
                    },
                    {
                        "schema_name": "mart_sales",
                        "table_name": "dim_customer",
                        "column_name": "customer_key",
                    },
                    {
                        "schema_name": "mart_sales",
                        "table_name": "dim_customer",
                        "column_name": "customer_name",
                    },
                ]
            )
            columns_path.write_text(
                json.dumps(columns, ensure_ascii=False),
                encoding="utf-8",
            )

            relationships_path = structure_dir / "relationships.json"
            relationships = json.loads(
                relationships_path.read_text(encoding="utf-8")
            )
            relationships.extend(
                [
                    {
                        "relationship_type": "primary_key",
                        "schema_name": "mart_sales",
                        "table_name": "dim_customer",
                        "column_names": ["customer_key"],
                        "constraint_name": "dim_customer_pkey",
                    },
                    {
                        "relationship_type": "foreign_key",
                        "schema_name": "mart_sales",
                        "table_name": "fct_sales_order_line",
                        "column_names": ["customer_key"],
                        "referenced_schema": "mart_sales",
                        "referenced_table": "dim_customer",
                        "referenced_column_names": ["customer_key"],
                        "constraint_name": "fk_fct_sales_customer",
                    },
                ]
            )
            relationships_path.write_text(
                json.dumps(relationships, ensure_ascii=False),
                encoding="utf-8",
            )

            context = load_query_context(structure_dir, metrics_path)

        self.assertEqual(len(context.join_constraints), 1)
        constraint = context.join_constraints[0]
        self.assertEqual(constraint.source_table, "mart_sales.fct_sales_order_line")
        self.assertEqual(constraint.source_columns, ("customer_key",))
        self.assertEqual(constraint.target_table, "mart_sales.dim_customer")
        self.assertEqual(constraint.target_columns, ("customer_key",))
        self.assertEqual(
            constraint.uniqueness_basis,
            "primary_key:dim_customer_pkey",
        )


if __name__ == "__main__":
    unittest.main()
