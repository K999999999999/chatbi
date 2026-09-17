"""Evaluation Runner（评测运行器）与汇总测试。"""

import unittest

from src.evaluation.evaluator import EvaluationCase
from src.online_query.contracts import (
    QueryContext,
    QueryData,
    QueryErrorCode,
    QueryFailure,
    QueryRequest,
    QuerySuccess,
    ValidatedSQL,
)


class _FakeService:
    def __init__(self, responses: dict[str, object]) -> None:
        self._responses = responses
        self.calls: list[QueryRequest] = []

    def query(self, request: QueryRequest) -> object:
        self.calls.append(request)
        response = self._responses[request.question]
        if isinstance(response, Exception):
            raise response
        return response


class _FakeExecutor:
    def __init__(self, result: QueryData | Exception) -> None:
        self._result = result
        self.calls: list[ValidatedSQL] = []

    def execute(self, sql: ValidatedSQL) -> QueryData:
        self.calls.append(sql)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class EvaluationRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.context = QueryContext(
            prompt_context="{}",
            allowed_tables=frozenset({"mart_sales.test_table"}),
            allowed_columns={"mart_sales.test_table": frozenset({"value"})},
        )
        self.reference = QueryData(
            columns=("value",),
            rows=((1,),),
            truncated=False,
        )

    def test_runs_existing_service_and_builds_summary(self) -> None:
        from src.evaluation.runner import CaseStatus, run_evaluation

        cases = (
            self._case("S01", "问题一", "simple"),
            self._case("M01", "问题二", "medium"),
        )
        service = _FakeService(
            {
                "问题一": self._success("evaluation-S01", rows=((1,),)),
                "问题二": self._success("evaluation-M01", rows=((2,),)),
            }
        )
        executor = _FakeExecutor(self.reference)

        run = run_evaluation(cases, service, executor, self.context)

        self.assertEqual(
            [result.status for result in run.cases],
            [CaseStatus.PASS, CaseStatus.FAIL],
        )
        self.assertEqual(
            [request.request_id for request in service.calls],
            ["evaluation-S01", "evaluation-M01"],
        )
        self.assertEqual(run.summary.total_cases, 2)
        self.assertEqual(run.summary.valid_cases, 2)
        self.assertEqual(run.summary.passed, 1)
        self.assertEqual(run.summary.failed, 1)
        self.assertEqual(run.summary.invalid_cases, 0)
        self.assertEqual(run.summary.execution_accuracy, 0.5)
        self.assertEqual(run.summary.category_accuracy["simple"], 1.0)
        self.assertEqual(run.summary.category_accuracy["medium"], 0.0)
        self.assertEqual(set(run.reference_results), {"S01", "M01"})

    def test_records_query_failure_and_continues_next_case(self) -> None:
        from src.evaluation.runner import CaseStatus, run_evaluation

        cases = (
            self._case("S01", "失败问题", "simple"),
            self._case("S02", "成功问题", "simple"),
        )
        service = _FakeService(
            {
                "失败问题": QueryFailure(
                    request_id="evaluation-S01",
                    error_code=QueryErrorCode.SQL_REJECTED,
                    error_message="生成的 SQL 未通过安全校验",
                    failure_stage="sql_guard",
                    internal_reason="SQL_REJECTED",
                ),
                "成功问题": self._success("evaluation-S02", rows=((1,),)),
            }
        )

        run = run_evaluation(cases, service, _FakeExecutor(self.reference), self.context)

        self.assertEqual(run.cases[0].status, CaseStatus.FAIL)
        self.assertEqual(run.cases[0].query_error_code, "SQL_REJECTED")
        self.assertEqual(run.cases[0].failure_stage, "sql_guard")
        self.assertEqual(run.cases[0].internal_reason, "SQL_REJECTED")
        self.assertEqual(run.cases[1].status, CaseStatus.PASS)
        self.assertEqual(len(service.calls), 2)

    def test_invalid_case_and_invalid_gold_sql_do_not_call_service(self) -> None:
        from src.evaluation.runner import CaseStatus, run_evaluation

        malformed = EvaluationCase(
            id="BAD01",
            schema_name="",
            category="unknown",
            question="",
            description="",
            expected_sql="",
            validation_error="缺少有效的 question",
        )
        rejected_gold = self._case(
            "BAD02",
            "危险标准SQL",
            "simple",
            expected_sql="DELETE FROM mart_sales.test_table;",
        )
        service = _FakeService({})
        executor = _FakeExecutor(self.reference)

        run = run_evaluation(
            (malformed, rejected_gold),
            service,
            executor,
            self.context,
        )

        self.assertEqual(
            [result.status for result in run.cases],
            [CaseStatus.INVALID_CASE, CaseStatus.INVALID_CASE],
        )
        self.assertEqual(service.calls, [])
        self.assertEqual(executor.calls, [])
        self.assertEqual(run.summary.valid_cases, 0)
        self.assertIsNone(run.summary.execution_accuracy)

    def test_gold_execution_failure_and_truncation_are_invalid(self) -> None:
        from src.evaluation.runner import CaseStatus, run_evaluation

        case = self._case("S01", "问题", "simple")
        service = _FakeService({"问题": self._success("evaluation-S01")})

        failed_run = run_evaluation(
            (case,),
            service,
            _FakeExecutor(RuntimeError("database failed")),
            self.context,
        )
        truncated_run = run_evaluation(
            (case,),
            service,
            _FakeExecutor(
                QueryData(columns=("value",), rows=((1,),), truncated=True)
            ),
            self.context,
        )

        self.assertEqual(failed_run.cases[0].status, CaseStatus.INVALID_CASE)
        self.assertEqual(truncated_run.cases[0].status, CaseStatus.INVALID_CASE)
        self.assertEqual(service.calls, [])

    def test_service_exception_and_truncated_system_result_do_not_stop_run(self) -> None:
        from src.evaluation.runner import CaseStatus, run_evaluation

        cases = (
            self._case("S01", "异常问题", "simple"),
            self._case("S02", "截断问题", "simple"),
            self._case("S03", "成功问题", "simple"),
        )
        service = _FakeService(
            {
                "异常问题": RuntimeError("unexpected"),
                "截断问题": self._success(
                    "evaluation-S02",
                    truncated=True,
                ),
                "成功问题": self._success("evaluation-S03"),
            }
        )

        run = run_evaluation(cases, service, _FakeExecutor(self.reference), self.context)

        self.assertEqual(
            [result.status for result in run.cases],
            [CaseStatus.FAIL, CaseStatus.INVALID_CASE, CaseStatus.PASS],
        )
        self.assertEqual(len(service.calls), 3)
        self.assertEqual(run.summary.valid_cases, 2)
        self.assertEqual(run.summary.execution_accuracy, 0.5)

    @staticmethod
    def _case(
        case_id: str,
        question: str,
        category: str,
        *,
        expected_sql: str = (
            "SELECT t.value FROM mart_sales.test_table AS t;"
        ),
    ) -> EvaluationCase:
        return EvaluationCase(
            id=case_id,
            schema_name="mart_sales",
            category=category,
            question=question,
            description="测试案例",
            expected_sql=expected_sql,
        )

    @staticmethod
    def _success(
        request_id: str,
        *,
        rows: tuple[tuple[object, ...], ...] = ((1,),),
        truncated: bool = False,
    ) -> QuerySuccess:
        return QuerySuccess(
            request_id=request_id,
            sql="SELECT 1",
            columns=("value",),
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
        )


if __name__ == "__main__":
    unittest.main()
