"""OnlineQueryService（在线查询服务）接入 Query Understanding 的测试。"""

from unittest.mock import Mock
import unittest

from src.online_query.contracts import (
    OnlineRetrievalResult,
    QueryContext,
    QueryData,
    QueryErrorCode,
    QueryFailure,
    QueryRequest,
    QuerySuccess,
    RequestShape,
    RetrievalStatus,
    RetrievalRequest,
)
from src.online_query.llm import LLMError
from src.online_query.query_understanding import (
    QueryType,
    ValidatedSemanticQuery,
    candidate_from_payload,
    validate_candidate,
)
from src.observability.contracts import TraceOutcome
from src.observability.tracing import create_in_memory_recorder
from src.online_query.service import OnlineQueryService


class QueryUnderstandingServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.context = QueryContext(
            prompt_context="DYNAMIC CONTEXT",
            allowed_tables=frozenset({"mart_sales.dim_customer"}),
            allowed_columns={"mart_sales.dim_customer": frozenset({"customer_name"})},
        )
        self.generator = Mock()
        self.generator.generate.return_value = (
            "SELECT customer_name FROM mart_sales.dim_customer"
        )
        self.executor = Mock()
        self.executor.execute.return_value = QueryData(
            columns=("customer_name",),
            rows=(("Alice",),),
            truncated=False,
        )
        self.adapter = Mock()
        self.adapter.understand.return_value = _candidate(
            query_type="entity_lookup",
            subjects=("客户",),
        )

    def test_success_passes_validated_semantic_query_to_retrieval(self) -> None:
        provider = Mock()
        provider.retrieve.return_value = OnlineRetrievalResult(
            status=RetrievalStatus.SUCCESS,
            query_context=self.context,
        )
        events: list[str] = []
        self.adapter.understand.side_effect = lambda question: (
            events.append("understand")
            or _candidate(
                query_type="metric_analysis",
                subjects=("销售",),
                metrics=("销售额", "毛利率"),
            )
        )
        provider.retrieve.side_effect = lambda request: (
            events.append("retrieve")
            or OnlineRetrievalResult(
                status=RetrievalStatus.SUCCESS,
                query_context=self.context,
            )
        )
        service = self._service(provider)

        result = service.execute(QueryRequest(question="完全不同的用户原话"))

        self.assertIsInstance(result, QuerySuccess)
        self.assertEqual(events, ["understand", "retrieve"])
        retrieval_request = provider.retrieve.call_args.args[0]
        self.assertIsInstance(retrieval_request, RetrievalRequest)
        assert isinstance(retrieval_request, RetrievalRequest)
        self.assertIsInstance(
            retrieval_request.semantic_query,
            ValidatedSemanticQuery,
        )
        self.assertEqual(
            retrieval_request.semantic_query.query_type,
            QueryType.METRIC_ANALYSIS,
        )
        self.assertEqual(retrieval_request.semantic_query.metrics, ("销售额", "毛利率"))
        self.assertEqual(retrieval_request.question, "完全不同的用户原话")
        self.assertEqual(retrieval_request.request_shape, RequestShape.EXPLICIT_MULTI)
        prompt = self.generator.generate.call_args.args[0]
        self.assertIn('"metrics":["销售额","毛利率"]', prompt)

    def test_prevalidated_semantic_query_skips_understanding(self) -> None:
        provider = Mock()
        provider.retrieve.return_value = OnlineRetrievalResult(
            status=RetrievalStatus.SUCCESS,
            query_context=self.context,
        )
        semantic_query = validate_candidate(
            _candidate(
                query_type="metric_analysis",
                subjects=("销售",),
                metrics=("毛利率",),
            ),
            original_question="改看毛利率",
        )
        service = self._service(provider)

        result = service.execute(
            QueryRequest(
                question="改看毛利率",
                semantic_query=semantic_query,
            )
        )

        self.assertIsInstance(result, QuerySuccess)
        self.adapter.understand.assert_not_called()
        retrieval_request = provider.retrieve.call_args.args[0]
        self.assertEqual(retrieval_request.semantic_query, semantic_query)
        assert isinstance(result, QuerySuccess)
        self.assertEqual(result.semantic_query, semantic_query)

    def test_query_understanding_failure_stops_before_retrieval_sql_and_database(
        self,
    ) -> None:
        provider = Mock()
        self.adapter.understand.side_effect = LLMError("provider detail")
        service = self._service(provider)

        result = service.execute(QueryRequest(question="查询客户"))

        self._assert_failure(result, QueryErrorCode.LLM_ERROR)
        assert isinstance(result, QueryFailure)
        self.assertNotIn(QueryErrorCode.LLM_ERROR.value, result.error_message)
        self.assertEqual(result.failure_stage, "query_understanding")
        self.assertEqual(result.internal_reason, "UNDERSTANDING_FAILED")
        provider.retrieve.assert_not_called()
        self.generator.generate.assert_not_called()
        self.executor.execute.assert_not_called()

    def test_semantic_rejection_stops_before_retrieval_sql_and_database(self) -> None:
        provider = Mock()
        self.adapter.understand.return_value = _candidate(
            query_type="unknown",
            subjects=(),
        )
        service = self._service(provider)

        result = service.execute(QueryRequest(question="随便聊聊天"))

        self._assert_failure(result, QueryErrorCode.CANNOT_ANSWER)
        assert isinstance(result, QueryFailure)
        self.assertEqual(result.error_message, "无法确定查询类型")
        self.assertEqual(result.failure_stage, "query_understanding")
        self.assertEqual(result.internal_reason, "QUERY_TYPE_UNKNOWN")
        provider.retrieve.assert_not_called()
        self.generator.generate.assert_not_called()
        self.executor.execute.assert_not_called()

    def test_missing_query_understanding_adapter_is_online_configuration_error(
        self,
    ) -> None:
        provider = Mock()
        service = OnlineQueryService(
            self.generator,
            self.executor,
            retrieval_provider=provider,
        )

        result = service.execute(QueryRequest(question="查询客户"))

        self._assert_failure(result, QueryErrorCode.LLM_ERROR)
        provider.retrieve.assert_not_called()
        self.generator.generate.assert_not_called()
        self.executor.execute.assert_not_called()

    def test_query_understanding_trace_keeps_internal_reason(self) -> None:
        recorder, exporter = create_in_memory_recorder()
        self.adapter.understand.return_value = _candidate(
            query_type="unknown",
            subjects=(),
        )
        service = OnlineQueryService(
            self.generator,
            self.executor,
            retrieval_provider=Mock(),
            query_understanding=self.adapter,
            trace_recorder=recorder,
        )

        result = service.execute(QueryRequest(question="随便聊聊天"))

        self._assert_failure(result, QueryErrorCode.CANNOT_ANSWER)
        span = next(
            item
            for item in exporter.get_finished_spans()
            if item.name == "query.understanding"
        )
        self.assertEqual(
            span.attributes["chatbi.query_understanding.reason"],
            "QUERY_TYPE_UNKNOWN",
        )
        self.assertEqual(
            span.attributes["chatbi.outcome"],
            TraceOutcome.BUSINESS_REJECTION.value,
        )

    def _service(self, provider: Mock) -> OnlineQueryService:
        return OnlineQueryService(
            self.generator,
            self.executor,
            retrieval_provider=provider,
            query_understanding=self.adapter,
        )

    def _assert_failure(self, result: object, error_code: QueryErrorCode) -> None:
        self.assertIsInstance(result, QueryFailure)
        assert isinstance(result, QueryFailure)
        self.assertEqual(result.error_code, error_code)


def _candidate(
    *,
    query_type: str,
    subjects: tuple[str, ...],
    metrics: tuple[str, ...] = (),
):
    return candidate_from_payload(
        {
            "query_type": query_type,
            "subjects": list(subjects),
            "metrics": list(metrics),
            "dimensions": [],
            "time": None,
            "filters": [],
        }
    )


if __name__ == "__main__":
    unittest.main()
