"""Online Retrieval 与 OnlineQueryService（在线查询服务）集成测试。"""

from unittest.mock import Mock
import unittest

from src.online_query.context import ContextLoadError
from src.online_query.contracts import (
    OnlineRetrievalResult,
    QueryContext,
    QueryData,
    QueryErrorCode,
    QueryFailure,
    QueryRequest,
    QuerySuccess,
    RetrievalStatus,
)
from src.online_query.service import OnlineQueryService


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

    def test_technical_retrieval_failure_falls_back_to_static_context(self) -> None:
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

        self.assertIsInstance(result, QuerySuccess)
        prompt = self.generator.generate.call_args.args[0]
        self.assertIn("STATIC CONTEXT", prompt)
        self.assertIn("status=RETRIEVAL_UNAVAILABLE", logs.output[0])
        self.assertIn("reason=qdrant unavailable", logs.output[0])

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
        )

    def _assert_failure(self, result: object, error_code: QueryErrorCode) -> None:
        self.assertIsInstance(result, QueryFailure)
        assert isinstance(result, QueryFailure)
        self.assertEqual(result.error_code, error_code)


if __name__ == "__main__":
    unittest.main()
