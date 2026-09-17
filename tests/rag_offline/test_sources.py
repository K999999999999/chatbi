"""RAG Offline 事实源加载与校验测试。"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.rag_offline import (
    DEFAULT_METRICS_PATH,
    DEFAULT_STRUCTURE_DIR,
    SourceLoadError,
    load_facts,
)


class SourceLoadingTest(unittest.TestCase):
    def test_loads_default_generated_facts(self) -> None:
        facts = load_facts()

        self.assertEqual(len(facts.tables), 7)
        self.assertEqual(len(facts.columns), 69)
        self.assertEqual(len(facts.relationships), 25)
        self.assertEqual(len(facts.metrics), 6)

        line_count = next(
            metric
            for metric in facts.metrics
            if metric["name"] == "已完成订单明细行数"
        )
        self.assertEqual(line_count["formula"], "COUNT(*)")
        self.assertEqual(line_count["aliases"], ("订单明细行数",))

    def test_loads_valid_temporary_facts(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)

            facts = load_facts(root, root / "metrics.json")

        self.assertEqual(len(facts.tables), 2)
        self.assertEqual(len(facts.columns), 6)
        self.assertEqual(len(facts.metrics), 2)
        self.assertEqual(facts.metrics[1]["depends_on"], ("已完成订单数",))
        self.assertNotIn("sql_template", facts.metrics[0])

    def test_empty_file_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)
            (root / "tables.json").write_text("[]", encoding="utf-8")

            with self.assertRaisesRegex(SourceLoadError, "必须是非空"):
                load_facts(root, root / "metrics.json")

    def test_duplicate_table_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)
            records = json.loads((root / "tables.json").read_text(encoding="utf-8"))
            records.append(records[0])
            (root / "tables.json").write_text(
                json.dumps(records, ensure_ascii=False),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(SourceLoadError, "重复表"):
                load_facts(root, root / "metrics.json")

    def test_column_without_table_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)
            records = json.loads((root / "columns.json").read_text(encoding="utf-8"))
            records.append(
                {
                    "schema_name": "mart_sales",
                    "table_name": "missing_table",
                    "column_name": "value",
                    "data_type": "text",
                }
            )
            (root / "columns.json").write_text(
                json.dumps(records, ensure_ascii=False),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(SourceLoadError, "不存在的表"):
                load_facts(root, root / "metrics.json")

    def test_metric_with_missing_dependency_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)
            metrics = json.loads((root / "metrics.json").read_text(encoding="utf-8"))
            metrics[1]["depends_on"] = ["不存在的指标"]
            (root / "metrics.json").write_text(
                json.dumps(metrics, ensure_ascii=False),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(SourceLoadError, "依赖不存在的指标"):
                load_facts(root, root / "metrics.json")

    def test_metric_with_missing_time_column_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)
            metrics = json.loads((root / "metrics.json").read_text(encoding="utf-8"))
            metrics[0]["time_field"] = "fct_sales.missing_date -> dim_date.full_date"
            (root / "metrics.json").write_text(
                json.dumps(metrics, ensure_ascii=False),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(SourceLoadError, "时间字段引用"):
                load_facts(root, root / "metrics.json")


def _write_facts(root: Path) -> None:
    (root / "tables.json").write_text(
        json.dumps(
            [
                {
                    "schema_name": "mart_sales",
                    "table_name": "dim_date",
                    "table_type": "BASE TABLE",
                    "description": "日期维度表",
                },
                {
                    "schema_name": "mart_sales",
                    "table_name": "fct_sales",
                    "table_type": "BASE TABLE",
                    "description": "销售事实表",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "columns.json").write_text(
        json.dumps(
            [
                {
                    "schema_name": "mart_sales",
                    "table_name": "dim_date",
                    "column_name": "date_key",
                    "data_type": "int",
                    "description": "日期代理键",
                    "is_primary_key": True,
                    "is_foreign_key": False,
                },
                {
                    "schema_name": "mart_sales",
                    "table_name": "dim_date",
                    "column_name": "full_date",
                    "data_type": "date",
                    "description": "自然日期",
                },
                {
                    "schema_name": "mart_sales",
                    "table_name": "fct_sales",
                    "column_name": "order_id",
                    "data_type": "text",
                    "description": "订单标识",
                },
                {
                    "schema_name": "mart_sales",
                    "table_name": "fct_sales",
                    "column_name": "order_status",
                    "data_type": "text",
                    "description": "订单状态",
                    "value_examples": ["completed", "pending"],
                },
                {
                    "schema_name": "mart_sales",
                    "table_name": "fct_sales",
                    "column_name": "amount",
                    "data_type": "numeric",
                    "description": "销售金额",
                },
                {
                    "schema_name": "mart_sales",
                    "table_name": "fct_sales",
                    "column_name": "completion_date_key",
                    "data_type": "int",
                    "description": "完成日期代理键",
                    "is_foreign_key": True,
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "relationships.json").write_text(
        json.dumps(
            [
                {
                    "relationship_type": "foreign_key",
                    "schema_name": "mart_sales",
                    "table_name": "fct_sales",
                    "column_names": ["completion_date_key"],
                    "referenced_schema": "mart_sales",
                    "referenced_table": "dim_date",
                    "referenced_column_names": ["date_key"],
                    "constraint_name": "fk_fct_sales_date",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "metrics.json").write_text(
        json.dumps(
            [
                {
                    "name": "已完成订单数",
                    "level": "原子指标",
                    "aliases": ["完成订单数"],
                    "definition": "已完成状态的订单数量。",
                    "formula": "COUNT(DISTINCT f.order_id)",
                    "sql_template": "SELECT COUNT(*) FROM fct_sales;",
                    "data_source": "mart_sales.fct_sales",
                    "depends_on": [],
                    "filters": ["f.order_status = 'completed'"],
                    "notes": "按 order_id 去重。",
                    "time_field": "fct_sales.completion_date_key -> dim_date.full_date",
                },
                {
                    "name": "销售金额",
                    "level": "原子指标",
                    "aliases": ["销售额"],
                    "definition": "已完成订单销售金额之和。",
                    "formula": "SUM(f.amount)",
                    "data_source": "mart_sales.fct_sales",
                    "depends_on": ["已完成订单数"],
                    "filters": ["f.order_status = 'completed'"],
                    "notes": "",
                    "time_field": "fct_sales.completion_date_key -> dim_date.full_date",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
