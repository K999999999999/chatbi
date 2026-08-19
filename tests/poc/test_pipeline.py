"""POC 编排链路测试。"""

from pathlib import Path
import unittest

from src.poc.context import ContextBuilder
from src.poc.executor import QueryResult
from src.poc.pipeline import PocQueryPipeline
from src.poc.semantic import MetricCatalog
from src.poc.sql_generator import RuleBasedSqlGenerator
from src.poc.sql_guard import SqlGuard
from src.poc.structure import StructureCatalog


ROOT = Path(__file__).resolve().parents[2]


class _FakeExecutor:
    def execute(self, sql):  # type: ignore[no-untyped-def]
        return QueryResult(
            columns=("sales_revenue",),
            rows=((123.45,),),
        )


class PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        structure = StructureCatalog.from_directory(
            ROOT / "src" / "poc" / "structure" / "generated"
        )
        metrics = MetricCatalog.from_file(
            ROOT / "src" / "poc" / "semantic" / "metrics.json"
        )
        metrics.validate_against_structure(structure)
        cls.pipeline = PocQueryPipeline(
            context_builder=ContextBuilder(structure, metrics),
            sql_generator=RuleBasedSqlGenerator(),
            sql_guard=SqlGuard(structure),
            executor=_FakeExecutor(),
        )

    def test_successful_chain_returns_sql_and_rows(self) -> None:
        response = self.pipeline.run("查询 2025 年的销售额")
        self.assertTrue(response.success)
        self.assertEqual(("sales_revenue",), response.metric_codes)
        self.assertIn("mart_sales", response.sql or "")
        self.assertEqual(((123.45,),), response.rows)

    def test_unsupported_metric_is_a_controlled_failure(self) -> None:
        response = self.pipeline.run("查询 2025 年的净利润")
        self.assertFalse(response.success)
        self.assertIsNotNone(response.error)
        self.assertIsNone(response.sql)


if __name__ == "__main__":
    unittest.main()
