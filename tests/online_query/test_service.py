"""OnlineQueryService（在线查询服务）编排与错误边界测试。"""

import unittest
from unittest.mock import Mock, patch
from uuid import UUID

import src.online_query.sql_guard as sql_guard
from src.online_query.context import ContextLoadError
from src.online_query.contracts import (
    QueryContext,
    QueryData,
    QueryErrorCode,
    QueryFailure,
    QueryRequest,
    QuerySuccess,
    ValidatedSQL,
)
from src.online_query.database import DatabaseError, DatabaseQueryTimeout
from src.online_query.llm import LLMError
from src.online_query.service import OnlineQueryService


class ServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.context = QueryContext(
            prompt_context=(
                '{"tables": [{"schema_name": "mart_sales", '
                '"table_name": "fct_sales_order_line"}]}'
            ),
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

    def test_success_runs_full_chain_and_returns_result(self) -> None:
        service = self._service()

        result = service.execute(
            QueryRequest(question=" 查询已完成订单 ", request_id=" req-1 ")
        )

        self.assertIsInstance(result, QuerySuccess)
        assert isinstance(result, QuerySuccess)
        self.assertEqual(result.request_id, "req-1")
        self.assertEqual(result.sql, self.sql)
        self.assertEqual(result.columns, ("order_id",))
        self.assertEqual(result.rows, (("SO-001",),))
        self.assertEqual(result.row_count, 1)
        self.assertFalse(result.truncated)
        prompt = self.generator.generate.call_args.args[0]
        self.assertIn("查询已完成订单", prompt)
        self.executor.execute.assert_called_once_with(ValidatedSQL(self.sql))

    def test_missing_request_id_is_generated(self) -> None:
        result = self._service().execute(QueryRequest(question="查询订单"))

        self.assertIsInstance(result, QuerySuccess)
        assert isinstance(result, QuerySuccess)
        UUID(result.request_id)

    def test_invalid_question_stops_before_llm(self) -> None:
        result = self._service().execute(
            QueryRequest(question="   ", request_id="req-invalid")
        )

        self._assert_failure(result, QueryErrorCode.INVALID_REQUEST)
        self.generator.generate.assert_not_called()
        self.executor.execute.assert_not_called()

    def test_context_failure_stops_before_llm(self) -> None:
        loader = Mock(side_effect=ContextLoadError("file detail"))
        service = OnlineQueryService(
            self.generator,
            self.executor,
            context_loader=loader,
        )

        result = service.execute(QueryRequest(question="查询订单"))

        self._assert_failure(result, QueryErrorCode.CONTEXT_ERROR)
        loader.assert_called_once_with()
        self.generator.generate.assert_not_called()
        self.executor.execute.assert_not_called()

    def test_context_is_loaded_only_when_service_is_created(self) -> None:
        loader = Mock(return_value=self.context)
        service = OnlineQueryService(
            self.generator,
            self.executor,
            context_loader=loader,
        )

        service.execute(QueryRequest(question="第一次查询"))
        service.execute(QueryRequest(question="第二次查询"))

        loader.assert_called_once_with()

    def test_llm_failure_stops_before_sql_guard_and_database(self) -> None:
        self.generator.generate.side_effect = LLMError("provider detail")
        service = self._service()

        with patch("src.online_query.service._new_validation_session") as guard:
            result = service.execute(QueryRequest(question="查询订单"))

        self._assert_failure(result, QueryErrorCode.LLM_ERROR)
        guard.assert_not_called()
        self.generator.generate.assert_called_once()
        self.executor.execute.assert_not_called()

    def test_query_understanding_reason_reaches_controlled_failure(self) -> None:
        query_understanding = Mock()
        query_understanding.understand.side_effect = LLMError(
            "Query Understanding 返回的不是合法 JSON",
            reason="RESPONSE_NOT_JSON",
        )
        retrieval_provider = Mock()
        service = OnlineQueryService(
            self.generator,
            self.executor,
            context_loader=lambda: self.context,
            retrieval_provider=retrieval_provider,
            query_understanding=query_understanding,
        )

        result = service.execute(QueryRequest(question="查询订单"))

        self._assert_failure(result, QueryErrorCode.LLM_ERROR)
        assert isinstance(result, QueryFailure)
        self.assertEqual(result.failure_stage, "query_understanding")
        self.assertEqual(result.internal_reason, "RESPONSE_NOT_JSON")
        retrieval_provider.retrieve.assert_not_called()

    def test_llm_timeout_is_an_error_without_retry(self) -> None:
        self.generator.generate.side_effect = TimeoutError("provider detail")

        result = self._service().execute(QueryRequest(question="查询订单"))

        self._assert_failure(result, QueryErrorCode.LLM_ERROR)
        self.generator.generate.assert_called_once()
        self.executor.execute.assert_not_called()

    def test_cannot_answer_stops_before_sql_guard_and_database(self) -> None:
        self.generator.generate.return_value = "CANNOT_ANSWER"
        service = self._service()

        with patch("src.online_query.service._new_validation_session") as guard:
            result = service.execute(QueryRequest(question="查询不存在的业务"))

        self._assert_failure(result, QueryErrorCode.CANNOT_ANSWER)
        guard.assert_not_called()
        self.executor.execute.assert_not_called()

    def test_query_reuses_one_parse_between_scope_and_sql_guard(self) -> None:
        with patch(
            "src.online_query.sql_guard.sql_guard._parse_single_select",
            wraps=sql_guard._parse_single_select,
        ) as parse:
            result = self._service().execute(QueryRequest(question="查询订单"))

        self.assertIsInstance(result, QuerySuccess)
        self.assertEqual(parse.call_count, 1)

    def test_separate_queries_do_not_reuse_validation_state(self) -> None:
        service = self._service()

        with patch(
            "src.online_query.sql_guard.sql_guard._parse_single_select",
            wraps=sql_guard._parse_single_select,
        ) as parse:
            first = service.execute(QueryRequest(question="第一次查询"))
            second = service.execute(QueryRequest(question="第二次查询"))

        self.assertIsInstance(first, QuerySuccess)
        self.assertIsInstance(second, QuerySuccess)
        self.assertEqual(parse.call_count, 2)

    def test_rejected_sql_stops_before_database(self) -> None:
        self.generator.generate.return_value = (
            "DELETE FROM mart_sales.fct_sales_order_line"
        )

        result = self._service().execute(QueryRequest(question="删除订单"))

        self._assert_failure(result, QueryErrorCode.SQL_REJECTED)
        self.executor.execute.assert_not_called()

    def test_database_timeout_maps_to_query_timeout(self) -> None:
        self.executor.execute.side_effect = DatabaseQueryTimeout("detail")

        result = self._service().execute(QueryRequest(question="查询订单"))

        self._assert_failure(result, QueryErrorCode.QUERY_TIMEOUT)
        self.executor.execute.assert_called_once()

    def test_database_failure_maps_to_database_error(self) -> None:
        self.executor.execute.side_effect = DatabaseError("detail")

        result = self._service().execute(QueryRequest(question="查询订单"))

        self._assert_failure(result, QueryErrorCode.DATABASE_ERROR)

    def test_empty_database_result_is_success(self) -> None:
        self.executor.execute.return_value = QueryData(
            columns=("order_id",),
            rows=(),
            truncated=False,
        )

        result = self._service().execute(QueryRequest(question="查询订单"))

        self.assertIsInstance(result, QuerySuccess)
        assert isinstance(result, QuerySuccess)
        self.assertEqual(result.row_count, 0)
        self.assertEqual(result.rows, ())

    def _service(self) -> OnlineQueryService:
        return OnlineQueryService(
            self.generator,
            self.executor,
            context_loader=lambda: self.context,
        )

    def _assert_failure(
        self,
        result: QuerySuccess | QueryFailure,
        error_code: QueryErrorCode,
    ) -> None:
        self.assertIsInstance(result, QueryFailure)
        assert isinstance(result, QueryFailure)
        self.assertEqual(result.error_code, error_code)
        self.assertTrue(result.request_id)
        self.assertTrue(result.error_message)
        self.assertNotIn("detail", result.error_message)


if __name__ == "__main__":
    unittest.main()
