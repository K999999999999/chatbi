"""Online Query（在线查询）核心 Contract（契约）测试。"""

from dataclasses import FrozenInstanceError
import unittest

from src.online_query.contracts import (
    QueryErrorCode,
    QueryRequest,
    QuerySuccess,
    RetrievalConfig,
)


class ContractTest(unittest.TestCase):
    def test_error_codes_match_module_spec(self) -> None:
        self.assertEqual(
            {code.value for code in QueryErrorCode},
            {
                "INVALID_REQUEST",
                "CONTEXT_ERROR",
                "LLM_ERROR",
                "CANNOT_ANSWER",
                "SQL_REJECTED",
                "DATABASE_ERROR",
                "QUERY_TIMEOUT",
            },
        )

    def test_contract_values_are_immutable(self) -> None:
        request = QueryRequest(question="查询销售额")
        success = QuerySuccess(
            request_id="req-1",
            sql="SELECT 1",
            columns=("value",),
            rows=((1,),),
            row_count=1,
            truncated=False,
        )

        with self.assertRaises(FrozenInstanceError):
            request.question = "修改问题"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            success.sql = "SELECT 2"  # type: ignore[misc]

    def test_v1_retrieval_defaults_match_confirmed_contract(self) -> None:
        config = RetrievalConfig()

        self.assertEqual(config.table_top_k, 5)
        self.assertEqual(config.column_top_k, 10)
        self.assertEqual(config.metric_top_k, 5)
        self.assertEqual(config.table_score_threshold, 0.30)
        self.assertEqual(config.column_score_threshold, 0.25)
        self.assertEqual(config.metric_score_threshold, 0.30)


if __name__ == "__main__":
    unittest.main()
