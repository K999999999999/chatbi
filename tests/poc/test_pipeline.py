"""POC 编排链路测试。"""

from pathlib import Path
import unittest

from src.poc.executor import QueryResult
from src.poc.llm_client import SqlGenerationError
from src.poc.pipeline import PocQueryPipeline
from src.poc.prompt_builder import PromptBuilder
from src.poc.query_parser import QueryParser
from src.poc.semantic import MetricCatalog
from src.poc.sql_guard import SqlGuard
from src.poc.structure import StructureCatalog


ROOT = Path(__file__).resolve().parents[2]


class _FakeExecutor:
    def execute(self, sql):  # type: ignore[no-untyped-def]
        return QueryResult(
            columns=("sales_revenue",),
            rows=((123.45,),),
        )


class _FakeLlmClient:
    def __init__(self, sql: str) -> None:
        self.sql = sql
        self.system_message = ""
        self.user_prompt = ""

    def generate_sql(self, system_message: str, user_prompt: str) -> str:
        self.system_message = system_message
        self.user_prompt = user_prompt
        return self.sql


class _FailingLlmClient:
    def generate_sql(self, system_message: str, user_prompt: str) -> str:
        raise SqlGenerationError("模拟 LLM 调用失败")


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
        cls.llm = _FakeLlmClient(
            "SELECT SUM(f.net_sales_amount_cny) AS sales_revenue "
            "FROM mart_sales.fct_sales_order_line AS f "
            "WHERE f.order_status = 'completed'"
        )
        cls.pipeline = PocQueryPipeline(
            query_parser=QueryParser(),
            prompt_builder=PromptBuilder(structure, metrics),
            llm_client=cls.llm,
            sql_guard=SqlGuard(structure),
            executor=_FakeExecutor(),
        )

    def test_successful_chain_returns_sql_and_rows(self) -> None:
        response = self.pipeline.run("查询 2025 年的销售额")
        self.assertTrue(response.success)
        self.assertEqual(("sales_revenue",), response.metric_codes)
        self.assertIn("mart_sales", response.sql or "")
        self.assertEqual(((123.45,),), response.rows)
        self.assertIn("net_sales_amount_cny", self.llm.user_prompt)
        self.assertIn("【指标知识】", self.llm.user_prompt)

    def test_llm_failure_is_a_controlled_failure(self) -> None:
        pipeline = PocQueryPipeline(
            query_parser=self.pipeline.query_parser,
            prompt_builder=self.pipeline.prompt_builder,
            llm_client=_FailingLlmClient(),
            sql_guard=self.pipeline.sql_guard,
            executor=self.pipeline.executor,
        )
        response = pipeline.run("查询 2025 年的销售额")
        self.assertFalse(response.success)
        self.assertIsNotNone(response.error)
        self.assertIsNone(response.sql)


if __name__ == "__main__":
    unittest.main()
