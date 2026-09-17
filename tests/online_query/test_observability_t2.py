"""T2 Online Query 主链路 Trace 的独立确定性测试。"""

from hashlib import sha256
import unittest
from unittest.mock import Mock, patch

from src.observability.contracts import TraceOutcome
from src.observability.tracing import create_in_memory_recorder
from src.online_query.context import ContextLoadError
from src.online_query.contracts import (
    FallbackPolicy,
    OnlineRetrievalResult,
    QueryContext,
    QueryData,
    QueryErrorCode,
    QueryFailure,
    QueryRequest,
    QuerySuccess,
    RequestShape,
    RetrievalStatus,
)
from src.online_query.database import DatabaseError, DatabaseQueryTimeout
from src.online_query.service import OnlineQueryService
from src.online_query.query_understanding import candidate_from_payload


class T2ObservabilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.context = QueryContext(
            prompt_context="SAFE CONTEXT",
            allowed_tables=frozenset({"mart_sales.fct_sales_order_line"}),
            allowed_columns={
                "mart_sales.fct_sales_order_line": frozenset(
                    {"order_id", "order_status"}
                )
            },
        )
        self.sql = (
            "SELECT order_id FROM mart_sales.fct_sales_order_line "
            "WHERE order_status = 'completed'"
        )
        self.generator = Mock()
        self.generator.generate.return_value = self.sql
        self.executor = Mock()
        self.executor.execute.return_value = QueryData(
            columns=("order_id",),
            rows=(("SO-001",),),
            truncated=False,
        )
        self.query_understanding = Mock()
        self.query_understanding.understand.side_effect = _candidate_for_question
        self.recorder, self.exporter = create_in_memory_recorder()

    def test_success_chain_has_one_root_shared_request_and_trace_id(self) -> None:
        result = self._service().query(
            QueryRequest(question="查询已完成订单", request_id="req-t2-success")
        )

        self.assertIsInstance(result, QuerySuccess)
        spans = self.exporter.get_finished_spans()
        self.assertEqual(
            [span.name for span in spans],
            [
                "request.validate",
                "prompt.build",
                "llm.generate",
                "candidate_scope.validate",
                "sql.guard",
                "database.execute",
                "query.request",
            ],
        )
        roots = [span for span in spans if span.name == "query.request"]
        self.assertEqual(len(roots), 1)
        root = roots[0]
        self.assertEqual(root.attributes["chatbi.request.id"], "req-t2-success")
        self.assertEqual(root.attributes["chatbi.request.source"], "INTERNAL")
        self.assertEqual(root.attributes["chatbi.outcome"], TraceOutcome.SUCCESS.value)
        self.assertEqual({span.context.trace_id for span in spans}, {root.context.trace_id})
        self.assertTrue(all(span.parent is not None for span in spans[:-1]))

        guard = next(span for span in spans if span.name == "sql.guard")
        self.assertEqual(
            guard.attributes["chatbi.sql.sha256"],
            sha256(self.sql.encode("utf-8")).hexdigest(),
        )
        self.assertNotIn(self.sql, repr(guard.attributes))

        database = next(span for span in spans if span.name == "database.execute")
        self.assertEqual(database.attributes["chatbi.database.row_count"], 1)
        self.assertFalse(database.attributes["chatbi.database.truncated"])
        self.assertNotIn("SAFE CONTEXT", repr(spans))

    def test_public_business_rejections_have_no_database_span(self) -> None:
        cases = (
            (
                "invalid",
                QueryRequest(question="   ", request_id="req-invalid"),
                QueryErrorCode.INVALID_REQUEST,
                {"request.validate"},
            ),
            (
                "cannot-answer",
                QueryRequest(question="查询不存在的业务", request_id="req-cannot"),
                QueryErrorCode.CANNOT_ANSWER,
                {"request.validate", "prompt.build", "llm.generate"},
            ),
            (
                "scope-rejected",
                QueryRequest(question="删除订单", request_id="req-scope"),
                QueryErrorCode.SQL_REJECTED,
                {
                    "request.validate",
                    "prompt.build",
                    "llm.generate",
                    "candidate_scope.validate",
                },
            ),
        )
        for name, request, error_code, expected_spans in cases:
            with self.subTest(name=name):
                self.exporter.clear()
                if error_code == QueryErrorCode.CANNOT_ANSWER:
                    self.generator.generate.return_value = "CANNOT_ANSWER"
                elif error_code == QueryErrorCode.SQL_REJECTED:
                    self.generator.generate.return_value = "DELETE FROM mart_sales.fct_sales_order_line"
                result = self._service().query(request)
                self._assert_failure(result, error_code)
                spans = self.exporter.get_finished_spans()
                names = {span.name for span in spans}
                self.assertTrue(expected_spans.issubset(names))
                self.assertNotIn("database.execute", names)
                root = next(span for span in spans if span.name == "query.request")
                self.assertEqual(
                    root.attributes["chatbi.outcome"],
                    TraceOutcome.BUSINESS_REJECTION.value,
                )
                self.assertEqual(root.attributes["chatbi.error_code"], error_code.value)

    def test_sql_guard_rejection_does_not_create_database_span(self) -> None:
        with patch(
            "src.online_query.service._new_validation_session",
        ) as factory:
            session = factory.return_value
            session.validate_sql.side_effect = RuntimeError("sql-internal-detail")
            result = self._service().query(QueryRequest(question="查询订单"))

        self._assert_failure(result, QueryErrorCode.SQL_REJECTED)
        names = {span.name for span in self.exporter.get_finished_spans()}
        self.assertIn("sql.guard", names)
        self.assertNotIn("database.execute", names)

    def test_technical_failures_and_database_timeout_are_classified(self) -> None:
        scenarios = (
            ("llm", self.generator, RuntimeError("provider-detail"), QueryErrorCode.LLM_ERROR, "llm.generate"),
            ("database", self.executor, DatabaseError("db-detail"), QueryErrorCode.DATABASE_ERROR, "database.execute"),
            ("timeout", self.executor, DatabaseQueryTimeout("timeout-detail"), QueryErrorCode.QUERY_TIMEOUT, "database.execute"),
        )
        for name, dependency, failure, error_code, span_name in scenarios:
            with self.subTest(name=name):
                self.exporter.clear()
                if dependency is self.generator:
                    self.generator.generate.side_effect = failure
                else:
                    self.executor.execute.side_effect = failure
                result = self._service().query(QueryRequest(question="查询订单"))
                self._assert_failure(result, error_code)
                spans = self.exporter.get_finished_spans()
                failed = next(span for span in spans if span.name == span_name)
                expected_outcome = (
                    TraceOutcome.TIMEOUT.value
                    if error_code == QueryErrorCode.QUERY_TIMEOUT
                    else TraceOutcome.TECHNICAL_FAILURE.value
                )
                self.assertEqual(failed.attributes["chatbi.outcome"], expected_outcome)
                self.assertEqual(failed.attributes["chatbi.error_code"], error_code.value)
                self.assertEqual(
                    next(span for span in spans if span.name == "query.request").attributes[
                        "chatbi.error_code"
                    ],
                    error_code.value,
                )
                self.generator.generate.side_effect = None
                self.executor.execute.side_effect = None

    def test_context_error_has_technical_root_without_unexecuted_nodes(self) -> None:
        service = OnlineQueryService(
            self.generator,
            self.executor,
            context_loader=Mock(side_effect=ContextLoadError("context-detail")),
            trace_recorder=self.recorder,
        )

        result = service.query(QueryRequest(question="查询订单"))

        self._assert_failure(result, QueryErrorCode.CONTEXT_ERROR)
        names = {span.name for span in self.exporter.get_finished_spans()}
        self.assertEqual(names, {"query.request", "request.validate"})
        root = next(
            span
            for span in self.exporter.get_finished_spans()
            if span.name == "query.request"
        )
        self.assertEqual(root.attributes["chatbi.outcome"], TraceOutcome.TECHNICAL_FAILURE.value)

    def test_retrieval_technical_failure_is_fail_closed_without_static_fallback(self) -> None:
        provider = Mock()
        provider.retrieve.return_value = OnlineRetrievalResult(
            status=RetrievalStatus.RETRIEVAL_UNAVAILABLE,
            asset_version="build-v2",
            warnings=("provider detail must not enter trace",),
        )
        result = self._service(provider).query(
            QueryRequest(question="查询订单", request_id="req-fallback")
        )

        self._assert_failure(result, QueryErrorCode.CONTEXT_ERROR)
        self.generator.generate.assert_not_called()
        self.executor.execute.assert_not_called()
        retrieval = next(
            span
            for span in self.exporter.get_finished_spans()
            if span.name == "retrieval.execute"
        )
        self.assertEqual(
            retrieval.attributes["chatbi.retrieval.request_shape"],
            RequestShape.BASELINE.value,
        )
        self.assertEqual(
            retrieval.attributes["chatbi.retrieval.fallback_policy"],
            FallbackPolicy.FAIL_CLOSED.value,
        )
        self.assertEqual(retrieval.attributes["chatbi.retrieval.status"], "RETRIEVAL_UNAVAILABLE")
        self.assertFalse(retrieval.attributes["chatbi.retrieval.fallback_used"])
        self.assertEqual(
            retrieval.attributes["chatbi.outcome"],
            TraceOutcome.TECHNICAL_FAILURE.value,
        )
        self.assertNotIn("provider detail must not enter trace", repr(retrieval))

    def test_retrieval_fail_closed_is_technical_and_stops_before_prompt(self) -> None:
        provider = Mock()
        provider.retrieve.return_value = OnlineRetrievalResult(
            status=RetrievalStatus.RETRIEVAL_UNAVAILABLE,
            request_shape=RequestShape.EXPLICIT_MULTI,
            fallback_policy=FallbackPolicy.FAIL_CLOSED,
        )

        result = self._service(provider).query(
            QueryRequest(question="按客户类型统计销售额和毛利率")
        )

        self._assert_failure(result, QueryErrorCode.CONTEXT_ERROR)
        spans = self.exporter.get_finished_spans()
        names = {span.name for span in spans}
        self.assertIn("retrieval.plan", names)
        self.assertIn("retrieval.execute", names)
        self.assertNotIn("prompt.build", names)
        retrieval = next(span for span in spans if span.name == "retrieval.execute")
        self.assertFalse(retrieval.attributes["chatbi.retrieval.fallback_used"])
        self.assertEqual(
            retrieval.attributes["chatbi.outcome"],
            TraceOutcome.TECHNICAL_FAILURE.value,
        )

    def test_trace_recorder_failure_does_not_change_query_result(self) -> None:
        class BrokenRecorder:
            def query_trace(self, *args, **kwargs):
                raise RuntimeError("trace-detail")

            def span(self, *args, **kwargs):
                raise RuntimeError("span-detail")

            def enrich_current(self, *args, **kwargs):
                raise RuntimeError("enrich-detail")

        request = QueryRequest(question="查询订单", request_id="req-trace-fault")
        expected = self._service().query(request)
        self.generator.reset_mock()
        self.executor.reset_mock()
        actual = self._service(trace_recorder=BrokenRecorder()).query(
            request
        )

        self.assertEqual(actual, expected)
        self.generator.generate.assert_called_once()
        self.executor.execute.assert_called_once()

    def _service(self, provider: Mock | None = None, *, trace_recorder=None) -> OnlineQueryService:
        return OnlineQueryService(
            self.generator,
            self.executor,
            context_loader=lambda: self.context,
            retrieval_provider=provider,
            query_understanding=self.query_understanding,
            trace_recorder=self.recorder if trace_recorder is None else trace_recorder,
        )

    def _assert_failure(self, result: object, error_code: QueryErrorCode) -> None:
        self.assertIsInstance(result, QueryFailure)
        assert isinstance(result, QueryFailure)
        self.assertEqual(result.error_code, error_code)


def _candidate_for_question(question: str):
    if "统计" in question and "和" in question:
        return candidate_from_payload(
            {
                "query_type": "metric_analysis",
                "subjects": ["业务主题"],
                "metrics": ["指标一", "指标二"],
                "dimensions": [],
                "time": None,
                "filters": [],
            }
        )
    return candidate_from_payload(
        {
            "query_type": "entity_lookup",
            "subjects": ["业务主题"],
            "metrics": [],
            "dimensions": [],
            "time": None,
            "filters": [],
        }
    )


if __name__ == "__main__":
    unittest.main()
