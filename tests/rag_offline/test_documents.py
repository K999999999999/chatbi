"""RAG Offline 三类检索文档生成测试。"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.rag_offline import (
    COLUMN_COLLECTION,
    METRIC_COLLECTION,
    TABLE_COLLECTION,
    RetrievalDocument,
    build_documents,
    load_facts,
)

from tests.rag_offline.test_sources import _write_facts


class DocumentBuildTest(unittest.TestCase):
    def test_builds_three_document_types_without_duplicates(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)
            facts = load_facts(root, root / "metrics.json")

            documents = build_documents(facts)

        self.assertEqual(len(documents), 2 + 6 + 2)
        ids = [document.document_id for document in documents]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(isinstance(document, RetrievalDocument) for document in documents))
        self.assertTrue(all(document.page_content for document in documents))
        self.assertEqual(
            sum(d.collection == TABLE_COLLECTION for d in documents),
            2,
        )
        self.assertEqual(
            sum(d.collection == COLUMN_COLLECTION for d in documents),
            6,
        )
        self.assertEqual(
            sum(d.collection == METRIC_COLLECTION for d in documents),
            2,
        )

    def test_table_document_contains_identity_and_description(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)
            facts = load_facts(root, root / "metrics.json")

            documents = [
                d for d in build_documents(facts) if d.collection == TABLE_COLLECTION
            ]

        table = documents[0]
        self.assertEqual(table.document_id, "table:mart_sales.dim_date")
        self.assertIn("表名：mart_sales.dim_date", table.page_content)
        self.assertIn("日期维度表", table.page_content)
        self.assertEqual(table.metadata["doc_type"], "TABLE")
        self.assertEqual(table.metadata["table_name"], "dim_date")

    def test_column_document_includes_value_examples_and_key_flags(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)
            facts = load_facts(root, root / "metrics.json")

            documents = [
                d for d in build_documents(facts) if d.collection == COLUMN_COLLECTION
            ]

        status = next(
            d for d in documents if d.metadata["column_name"] == "order_status"
        )
        date_key = next(
            d
            for d in documents
            if d.metadata["table_name"] == "fct_sales"
            and d.metadata["column_name"] == "completion_date_key"
        )
        self.assertIn("字段值示例：completed、pending", status.page_content)
        self.assertIn("外键", date_key.page_content)
        self.assertEqual(date_key.metadata["is_foreign_key"], True)
        self.assertIn("fct_sales", date_key.page_content)

    def test_metric_document_excludes_sql_template(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _write_facts(root)
            facts = load_facts(root, root / "metrics.json")

            documents = [
                d for d in build_documents(facts) if d.collection == METRIC_COLLECTION
            ]

        completed = next(
            d for d in documents if d.metadata["metric_name"] == "已完成订单数"
        )
        self.assertIn("指标定义：已完成状态的订单数量。", completed.page_content)
        self.assertIn("过滤条件：f.order_status = 'completed'", completed.page_content)
        self.assertNotIn("sql_template", completed.page_content)
        self.assertNotIn("SELECT COUNT(*)", completed.page_content)
        self.assertNotIn("sql_template", completed.metadata)
        self.assertEqual(completed.metadata["depends_on"], ())

        derived = next(
            d for d in documents if d.metadata["metric_name"] == "销售金额"
        )
        self.assertEqual(derived.metadata["depends_on"], ("已完成订单数",))
        self.assertIn("已完成订单数", derived.page_content)


if __name__ == "__main__":
    unittest.main()
