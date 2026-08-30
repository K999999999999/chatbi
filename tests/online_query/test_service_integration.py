"""Online Query（在线查询）真实依赖端到端验收。"""

import json
import os
from pathlib import Path
import unittest

from src.online_query.context import load_query_context
from src.online_query.contracts import QueryRequest, QuerySuccess
from src.online_query.database import PsycopgQueryExecutor
from src.online_query.llm import LangChainSQLGenerator
from src.online_query.service import OnlineQueryService
from src.online_query.sql_guard import validate_sql


class _FixedSQLGenerator:
    def __init__(self, sql: str) -> None:
        self._sql = sql

    def generate(self, prompt: str) -> str:
        return self._sql


@unittest.skipUnless(
    os.environ.get("RUN_DATABASE_TESTS") == "1",
    "需要显式启用本地 PostgreSQL 集成测试",
)
class ServiceDatabaseIntegrationTest(unittest.TestCase):
    def test_question_runs_through_service_guard_and_real_database(self) -> None:
        context = load_query_context()
        root = Path(__file__).resolve().parents[2]
        metrics = json.loads(
            (root / "src" / "semantic" / "metrics.json").read_text(
                encoding="utf-8"
            )
        )
        completed_orders_sql = metrics[0]["sql_template"]
        executor = PsycopgQueryExecutor.from_env()
        service = OnlineQueryService(
            _FixedSQLGenerator(completed_orders_sql),
            executor,
            context_loader=lambda: context,
        )

        result = service.query(
            QueryRequest(
                question="当前已完成订单数是多少？",
                request_id="e2e-database-chain",
            )
        )

        self.assertIsInstance(result, QuerySuccess, result)
        assert isinstance(result, QuerySuccess)
        self.assertEqual(result.row_count, 1)
        self.assertEqual(result.sql, completed_orders_sql)


@unittest.skipUnless(
    os.environ.get("RUN_LLM_TESTS") == "1",
    "需要显式启用真实 LLM 端到端测试",
)
class ServiceIntegrationTest(unittest.TestCase):
    def test_completed_order_count_matches_certified_metric_sql(self) -> None:
        context = load_query_context()
        generator = LangChainSQLGenerator.from_env()
        executor = PsycopgQueryExecutor.from_env()
        service = OnlineQueryService(
            generator,
            executor,
            context_loader=lambda: context,
        )
        root = Path(__file__).resolve().parents[2]
        metrics = json.loads(
            (root / "src" / "semantic" / "metrics.json").read_text(
                encoding="utf-8"
            )
        )
        completed_orders_sql = metrics[0]["sql_template"]
        expected = executor.execute(
            validate_sql(completed_orders_sql, context)
        )

        result = service.query(
            QueryRequest(
                question="当前已完成订单数是多少？",
                request_id="e2e-completed-orders",
            )
        )

        self.assertIsInstance(result, QuerySuccess, result)
        assert isinstance(result, QuerySuccess)
        self.assertEqual(result.rows, expected.rows)
        self.assertEqual(result.row_count, 1)


if __name__ == "__main__":
    unittest.main()
