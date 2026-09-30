"""多轮评测客户端通过正式 Query API/Application 会话入口执行。"""

import unittest
from decimal import Decimal

from evaluation.suites.multi_turn.multi_turn_api_client import QueryApiConversationClient
from src.online_query.contracts import (
    OnlineRetrievalResult,
    QueryContext,
    QueryData,
    RetrievalStatus,
    ValidatedSQL,
)
from src.online_query.query_understanding import (
    FilterCandidate,
    FilterOperator,
    QueryType,
    SemanticQueryCandidate,
    TimeCandidate,
    TimeGranularity,
)
from src.online_query.service import OnlineQueryService


class _Generator:
    def generate(self, prompt: str) -> str:
        del prompt
        return "SELECT t.value FROM mart_sales.test_table AS t;"


class _Executor:
    def execute(self, sql: ValidatedSQL) -> QueryData:
        del sql
        return QueryData(
            columns=("value",),
            rows=((Decimal("1.25"),),),
            truncated=False,
        )


class _Retrieval:
    def __init__(self, context: QueryContext) -> None:
        self.context = context

    def retrieve(self, request) -> OnlineRetrievalResult:
        del request
        return OnlineRetrievalResult(
            status=RetrievalStatus.SUCCESS,
            query_context=self.context,
        )


class _Understanding:
    def __init__(self) -> None:
        self.revision_calls = 0

    def understand(self, question: str) -> SemanticQueryCandidate:
        del question
        return SemanticQueryCandidate(
            query_type=QueryType.METRIC_ANALYSIS,
            subjects=(),
            metrics=("人民币净销售额",),
            dimensions=("销售区域",),
            time=TimeCandidate("2025年第一季度", TimeGranularity.QUARTER),
            filters=(
                FilterCandidate(
                    "客户类型",
                    FilterOperator.EQUALS,
                    ("enterprise",),
                ),
            ),
        )

    def understand_revision(self, previous, question: str) -> SemanticQueryCandidate:
        del previous, question
        self.revision_calls += 1
        return SemanticQueryCandidate(
            query_type=QueryType.METRIC_ANALYSIS,
            subjects=(),
            metrics=("人民币毛利",),
            dimensions=(),
            time=None,
            filters=(),
        )


class MultiTurnApiClientTest(unittest.TestCase):
    def test_uses_formal_query_api_and_preserves_same_session_id(self) -> None:
        context = QueryContext(
            prompt_context="{}",
            allowed_tables=frozenset({"mart_sales.test_table"}),
            allowed_columns={"mart_sales.test_table": frozenset({"value"})},
        )
        understanding = _Understanding()
        service = OnlineQueryService(
            _Generator(),
            _Executor(),
            context_loader=lambda: context,
            retrieval_provider=_Retrieval(context),
            query_understanding=understanding,
        )
        client = QueryApiConversationClient(
            service,
            query_understanding=understanding,
        )
        try:
            first = client.query(
                "2025 年第一季度按销售区域查询人民币净销售额",
                conversation_id=None,
                request_id="evaluation-MT01-T1",
            )
            second = client.query(
                "改看人民币毛利",
                conversation_id=first.conversation_id,
                request_id="evaluation-MT01-T2",
            )
        finally:
            client.close()

        self.assertEqual(first.conversation_id, second.conversation_id)
        self.assertIsNotNone(first.conversation_id)
        self.assertEqual(understanding.revision_calls, 1)
        self.assertEqual(second.result.rows, (("1.25",),))


if __name__ == "__main__":
    unittest.main()
