"""Online Retrieval 与 OnlineQueryService（在线查询服务）集成测试。"""

from unittest.mock import Mock
import unittest

from src.online_query.context import ContextLoadError
from src.online_query.contracts import (
    FallbackPolicy,
    JoinConstraint,
    MetricConstraint,
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
from src.online_query.service import OnlineQueryService
from src.online_query.query_understanding import candidate_from_payload


class RetrievalServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.static_context = QueryContext(
            prompt_context="STATIC CONTEXT",
            allowed_tables=frozenset({"mart_sales.fct_sales_order_line"}),
            allowed_columns={
                "mart_sales.fct_sales_order_line": frozenset({"order_id"})
            },
        )
        self.dynamic_context = QueryContext(
            prompt_context="DYNAMIC CONTEXT",
            allowed_tables=frozenset({"mart_sales.dim_customer"}),
            allowed_columns={
                "mart_sales.dim_customer": frozenset({"customer_name"})
            },
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
        self.query_understanding = Mock()
        self.query_understanding.understand.side_effect = _candidate_for_question

    def test_success_uses_dynamic_context_and_dynamic_scope(self) -> None:
        provider = Mock()
        provider.retrieve.return_value = OnlineRetrievalResult(
            status=RetrievalStatus.SUCCESS,
            query_context=self.dynamic_context,
        )
        service = self._service(provider)

        result = service.query(QueryRequest(question="查询客户"))

        self.assertIsInstance(result, QuerySuccess)
        assert isinstance(result, QuerySuccess)
        self.assertEqual(result.row_count, 1)
        prompt = self.generator.generate.call_args.args[0]
        self.assertIn("DYNAMIC CONTEXT", prompt)
        self.assertNotIn("STATIC CONTEXT", prompt)

    def test_business_retrieval_failure_returns_cannot_answer_before_llm(self) -> None:
        provider = Mock()
        provider.retrieve.return_value = OnlineRetrievalResult(
            status=RetrievalStatus.NO_REQUIRED_COLUMN_HIT
        )
        service = self._service(provider)

        result = service.query(QueryRequest(question="查询不存在的字段"))

        self._assert_failure(result, QueryErrorCode.CANNOT_ANSWER)
        self.generator.generate.assert_not_called()
        self.executor.execute.assert_not_called()

    def test_missing_relationship_or_candidate_returns_cannot_answer_before_llm(self) -> None:
        provider = Mock()
        service = self._service(provider)

        for status in (
            RetrievalStatus.NO_TABLE_HIT,
            RetrievalStatus.NO_METRIC_HIT,
            RetrievalStatus.PARTIAL_UNREACHABLE,
            RetrievalStatus.AMBIGUOUS,
        ):
            with self.subTest(status=status):
                provider.retrieve.return_value = OnlineRetrievalResult(status=status)
                result = service.query(QueryRequest(question="查询订单"))
                self._assert_failure(result, QueryErrorCode.CANNOT_ANSWER)

        self.generator.generate.assert_not_called()
        self.executor.execute.assert_not_called()

    def test_technical_retrieval_failure_returns_context_error(self) -> None:
        provider = Mock()
        provider.retrieve.return_value = OnlineRetrievalResult(
            status=RetrievalStatus.RETRIEVAL_UNAVAILABLE,
            asset_version="build-v2",
            warnings=("qdrant unavailable",),
        )
        self.generator.generate.return_value = (
            "SELECT order_id FROM mart_sales.fct_sales_order_line"
        )
        service = self._service(provider)

        with self.assertLogs("src.online_query.service", level="WARNING") as logs:
            result = service.query(QueryRequest(question="查询订单"))

        self._assert_failure(result, QueryErrorCode.CONTEXT_ERROR)
        self.generator.generate.assert_not_called()
        self.executor.execute.assert_not_called()
        self.assertIn("status=RETRIEVAL_UNAVAILABLE", logs.output[0])
        self.assertIn("reason=qdrant unavailable", logs.output[0])

    def test_asset_snapshot_failure_returns_context_error_without_llm(self) -> None:
        provider = Mock()
        provider.retrieve.return_value = OnlineRetrievalResult(
            status=RetrievalStatus.ASSET_UNAVAILABLE,
            warnings=("asset snapshot invalid",),
        )
        service = self._service(provider)

        result = service.query(QueryRequest(question="查询订单"))

        self._assert_failure(result, QueryErrorCode.CONTEXT_ERROR)
        self.generator.generate.assert_not_called()
        self.executor.execute.assert_not_called()

    def test_online_retrieval_failure_does_not_use_static_context(self) -> None:
        provider = Mock()
        provider.retrieve.return_value = OnlineRetrievalResult(
            status=RetrievalStatus.RETRIEVAL_UNAVAILABLE,
            asset_version="build-v2",
            warnings=("qdrant unavailable",),
        )
        service = self._service(provider)

        result = service.query(QueryRequest(question="查询订单"))

        self._assert_failure(result, QueryErrorCode.CONTEXT_ERROR)
        self.generator.generate.assert_not_called()
        self.executor.execute.assert_not_called()

    def test_online_retrieval_does_not_load_static_context(self) -> None:
        provider = Mock()
        provider.retrieve.return_value = OnlineRetrievalResult(
            status=RetrievalStatus.SUCCESS,
            query_context=self.dynamic_context,
        )
        loader = Mock(side_effect=AssertionError("在线模式不应加载静态上下文"))
        service = OnlineQueryService(
            self.generator,
            self.executor,
            context_loader=loader,
            retrieval_provider=provider,
            query_understanding=self.query_understanding,
        )

        result = service.query(QueryRequest(question="查询客户"))

        self.assertIsInstance(result, QuerySuccess)
        loader.assert_not_called()

    def test_multi_metric_technical_failure_does_not_fallback_to_static_context(self) -> None:
        provider = Mock()
        provider.retrieve.return_value = OnlineRetrievalResult(
            status=RetrievalStatus.RETRIEVAL_UNAVAILABLE,
            request_shape=RequestShape.EXPLICIT_MULTI,
            fallback_policy=FallbackPolicy.FAIL_CLOSED,
            warnings=("qdrant unavailable",),
        )
        service = self._service(provider)

        result = service.query(
            QueryRequest(question="按客户类型统计销售额和毛利率")
        )

        self._assert_failure(result, QueryErrorCode.CONTEXT_ERROR)
        self.generator.generate.assert_not_called()
        self.executor.execute.assert_not_called()
        retrieval_request = provider.retrieve.call_args.args[0]
        self.assertEqual(retrieval_request.request_shape, RequestShape.EXPLICIT_MULTI)
        self.assertEqual(
            retrieval_request.fallback_policy,
            FallbackPolicy.FAIL_CLOSED,
        )

    def test_multi_metric_provider_exception_does_not_fallback_to_static_context(self) -> None:
        provider = Mock()
        provider.retrieve.side_effect = RuntimeError("qdrant unavailable")
        service = self._service(provider)

        result = service.query(
            QueryRequest(question="按客户类型统计销售额和毛利率")
        )

        self._assert_failure(result, QueryErrorCode.CONTEXT_ERROR)
        self.generator.generate.assert_not_called()
        self.executor.execute.assert_not_called()

    def test_successful_provider_context_is_used_without_service_side_shape_branch(self) -> None:
        provider = Mock()
        provider.retrieve.return_value = OnlineRetrievalResult(
            status=RetrievalStatus.SUCCESS,
            request_shape=RequestShape.EXPLICIT_MULTI,
            query_context=self.dynamic_context,
        )
        service = self._service(provider)

        result = service.query(
            QueryRequest(question="按客户类型统计销售额和毛利率")
        )

        self.assertIsInstance(result, QuerySuccess)
        self.generator.generate.assert_called_once()
        self.executor.execute.assert_called_once()

    def test_multi_metric_success_runs_guard_before_database(self) -> None:
        provider = Mock()
        provider.retrieve.return_value = OnlineRetrievalResult(
            status=RetrievalStatus.SUCCESS,
            query_context=_multi_context(),
        )
        self.generator.generate.return_value = _valid_multi_sql()
        self.executor.execute.return_value = QueryData(
            columns=("customer_type", "completed_order_count", "net_sales_cny"),
            rows=(("Enterprise", 2, 100.0),),
            truncated=False,
        )
        service = self._service(provider)

        result = service.query(
            QueryRequest(question="按客户类型统计销售额和已完成订单数")
        )

        self.assertIsInstance(result, QuerySuccess)
        self.executor.execute.assert_called_once()

    def test_technical_failure_with_unavailable_static_context_is_context_error(self) -> None:
        provider = Mock()
        provider.retrieve.return_value = OnlineRetrievalResult(
            status=RetrievalStatus.EMBEDDING_UNAVAILABLE
        )
        service = OnlineQueryService(
            self.generator,
            self.executor,
            context_loader=Mock(side_effect=ContextLoadError("static unavailable")),
            retrieval_provider=provider,
            query_understanding=self.query_understanding,
        )

        result = service.query(QueryRequest(question="查询订单"))

        self._assert_failure(result, QueryErrorCode.CONTEXT_ERROR)
        self.generator.generate.assert_not_called()

    def test_dynamic_context_rejects_sql_outside_retrieval_scope(self) -> None:
        provider = Mock()
        provider.retrieve.return_value = OnlineRetrievalResult(
            status=RetrievalStatus.SUCCESS,
            query_context=self.dynamic_context,
        )
        self.generator.generate.return_value = (
            "SELECT order_id FROM mart_sales.fct_sales_order_line"
        )
        service = self._service(provider)

        result = service.query(QueryRequest(question="查询客户"))

        self._assert_failure(result, QueryErrorCode.SQL_REJECTED)
        self.executor.execute.assert_not_called()

    def _service(self, provider: Mock) -> OnlineQueryService:
        return OnlineQueryService(
            self.generator,
            self.executor,
            context_loader=lambda: self.static_context,
            retrieval_provider=provider,
            query_understanding=self.query_understanding,
        )

    def _assert_failure(self, result: object, error_code: QueryErrorCode) -> None:
        self.assertIsInstance(result, QueryFailure)
        assert isinstance(result, QueryFailure)
        self.assertEqual(result.error_code, error_code)


def _multi_context() -> QueryContext:
    fact_table = "mart_sales.fct_sales_order_line"
    customer_table = "mart_sales.dim_customer"
    return QueryContext(
        prompt_context="MULTI CONTEXT",
        allowed_tables=frozenset({fact_table, customer_table}),
        allowed_columns={
            fact_table: frozenset(
                {
                    "customer_key",
                    "order_id",
                    "net_sales_amount_cny",
                    "order_status",
                }
            ),
            customer_table: frozenset({"customer_key", "customer_type"}),
        },
        request_shape=RequestShape.EXPLICIT_MULTI,
        metric_constraints=(
            MetricConstraint(
                ordinal=1,
                requested_text="销售额",
                document_id="metric:net_sales",
                metric_name="人民币净销售额",
                formula="SUM(f.net_sales_amount_cny)",
                data_source=fact_table,
                time_field="fct_sales_order_line.completion_date_key -> dim_date.full_date",
                filters=("f.order_status = 'completed'",),
                depends_on=(),
            ),
            MetricConstraint(
                ordinal=2,
                requested_text="已完成订单数",
                document_id="metric:completed_orders",
                metric_name="已完成订单数",
                formula="COUNT(DISTINCT f.order_id)",
                data_source=fact_table,
                time_field="fct_sales_order_line.completion_date_key -> dim_date.full_date",
                filters=("f.order_status = 'completed'",),
                depends_on=(),
            ),
        ),
        join_constraints=(
            JoinConstraint(
                source_table=fact_table,
                source_columns=("customer_key",),
                target_table=customer_table,
                target_columns=("customer_key",),
                uniqueness_basis="primary_key:dim_customer",
                direction="forward",
            ),
        ),
    )


def _valid_multi_sql() -> str:
    return """
SELECT c.customer_type,
       SUM(f.net_sales_amount_cny) AS net_sales_cny,
       COUNT(DISTINCT f.order_id) AS completed_order_count
FROM mart_sales.fct_sales_order_line AS f
LEFT JOIN mart_sales.dim_customer AS c
  ON f.customer_key = c.customer_key
WHERE f.order_status = 'completed'
GROUP BY c.customer_type
""".strip()


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
