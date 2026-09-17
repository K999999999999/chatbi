"""T4B Evaluation Trace（评测链路）关联、共享 Root 和报告兼容性测试。"""

import json
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.observability import QuerySource, create_in_memory_recorder
from src.online_query.contracts import (
    QueryContext,
    QueryData,
    QueryErrorCode,
    QueryFailure,
    QueryRequest,
    QuerySuccess,
    ValidatedSQL,
)
from src.online_query.service import OnlineQueryService

from src.evaluation.evaluator import EvaluationCase
from src.evaluation.runner import CaseStatus, run_evaluation


TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")


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
    def __init__(self, result: QueryData) -> None:
        self.result = result
        self.calls: list[ValidatedSQL] = []

    def execute(self, sql: ValidatedSQL) -> QueryData:
        self.calls.append(sql)
        return self.result


class _FakeGenerator:
    def __init__(self, sql: str) -> None:
        self.sql = sql
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.sql


class EvaluationObservabilityT4BTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sql = "SELECT t.value FROM mart_sales.test_table AS t;"
        self.context = QueryContext(
            prompt_context="{}",
            allowed_tables=frozenset({"mart_sales.test_table"}),
            allowed_columns={
                "mart_sales.test_table": frozenset({"value"}),
            },
        )
        self.reference = QueryData(
            columns=("value",),
            rows=((1,),),
            truncated=False,
        )

    def test_all_online_result_branches_keep_request_and_trace_ids(self) -> None:
        recorder, exporter = create_in_memory_recorder()
        cases = (
            self._case("PASS", "pass"),
            self._case("FAIL", "mismatch"),
            self._case("QFAIL", "query failure"),
            self._case("UNEXPECTED", "unexpected"),
            self._case("EXCEPTION", "exception"),
            self._case("TRUNCATED", "truncated"),
            EvaluationCase(
                id="INVALID_FORMAT",
                schema_name="",
                category="unknown",
                question="",
                description="",
                expected_sql="",
                validation_error="案例格式错误",
            ),
            self._case(
                "INVALID_GOLD",
                "invalid gold",
                expected_sql="DELETE FROM mart_sales.test_table;",
            ),
        )
        service = _FakeService(
            {
                "pass": self._success(rows=((1,),)),
                "mismatch": self._success(rows=((2,),)),
                "query failure": QueryFailure(
                    request_id="evaluation-QFAIL",
                    error_code=QueryErrorCode.SQL_REJECTED,
                    error_message="SQL 被拒绝",
                ),
                "unexpected": object(),
                "exception": RuntimeError("must not enter report"),
                "truncated": self._success(truncated=True),
            }
        )
        executor = _FakeExecutor(self.reference)

        run = run_evaluation(
            cases,
            service,
            executor,
            self.context,
            trace_recorder=recorder,
        )

        by_id = {case.case_id: case for case in run.cases}
        for case_id in (
            "PASS",
            "FAIL",
            "QFAIL",
            "UNEXPECTED",
            "EXCEPTION",
            "TRUNCATED",
        ):
            result = by_id[case_id]
            self.assertEqual(result.request_id, f"evaluation-{case_id}")
            self.assertIsNotNone(result.trace_id)
            self.assertRegex(result.trace_id or "", TRACE_ID_RE)

        self.assertEqual(by_id["PASS"].status, CaseStatus.PASS)
        self.assertEqual(by_id["FAIL"].status, CaseStatus.FAIL)
        self.assertEqual(by_id["QFAIL"].status, CaseStatus.FAIL)
        self.assertEqual(by_id["UNEXPECTED"].status, CaseStatus.FAIL)
        self.assertEqual(by_id["EXCEPTION"].status, CaseStatus.FAIL)
        self.assertEqual(by_id["TRUNCATED"].status, CaseStatus.INVALID_CASE)
        for case_id in ("INVALID_FORMAT", "INVALID_GOLD"):
            self.assertEqual(by_id[case_id].status, CaseStatus.INVALID_CASE)
            self.assertIsNone(by_id[case_id].request_id)
            self.assertIsNone(by_id[case_id].trace_id)

        self.assertEqual(len(service.calls), 6)
        self.assertEqual(len(executor.calls), 6)
        self.assertEqual(len(exporter.get_finished_spans()), 6)

    def test_shared_recorder_has_one_evaluation_root_and_service_borrows_it(
        self,
    ) -> None:
        recorder, exporter = create_in_memory_recorder()
        generator = _FakeGenerator(self.sql)
        executor = _FakeExecutor(self.reference)
        service = OnlineQueryService(
            generator,
            executor,
            context_loader=lambda: self.context,
            trace_recorder=recorder,
        )

        run = run_evaluation(
            (self._case("SHARED", "共享 Root"),),
            service,
            executor,
            self.context,
            trace_recorder=recorder,
        )

        self.assertEqual(run.cases[0].status, CaseStatus.PASS)
        self.assertRegex(run.cases[0].trace_id or "", TRACE_ID_RE)
        spans = exporter.get_finished_spans()
        roots = [span for span in spans if span.name == "query.request"]
        self.assertEqual(len(roots), 1)
        root = roots[0]
        self.assertEqual(
            root.attributes["chatbi.request.source"],
            QuerySource.EVALUATION.value,
        )
        self.assertEqual(root.attributes["evaluation.case_id"], "SHARED")
        self.assertEqual(root.attributes["chatbi.request.id"], "evaluation-SHARED")
        self.assertTrue(
            all(span.context.trace_id == root.context.trace_id for span in spans)
        )

    def test_report_contains_safe_correlation_and_loads_old_baseline(self) -> None:
        from src.evaluation.reporting import (
            RunMetadata,
            compare_baseline,
            create_report,
            load_report,
            render_markdown_report,
        )

        recorder, _ = create_in_memory_recorder()
        service = _FakeService({"pass": self._success()})
        run = run_evaluation(
            (self._case("PASS", "pass"),),
            service,
            _FakeExecutor(self.reference),
            self.context,
            trace_recorder=recorder,
        )
        metadata = RunMetadata(
            run_id="run",
            created_at="2026-09-12T00:00:00Z",
            git_commit="abcdef1",
            git_dirty=False,
            model="test-model",
            temperature=0.1,
            max_tokens=1200,
            model_endpoint_hash="endpoint",
            test_set_hash="same-test",
            context_hash="context",
            reference_result_hash="same-reference",
        )
        report = create_report(run, metadata)
        case = report["cases"][0]
        self.assertIsInstance(case, dict)
        self.assertIn("request_id", case)
        self.assertIn("trace_id", case)

        markdown = render_markdown_report(report)
        self.assertIn("## 链路关联", markdown)
        self.assertIn("| PASS | evaluation-PASS |", markdown)
        self.assertNotIn("Prompt", markdown)
        self.assertNotIn("SELECT t.value", markdown)

        truncated_run = run_evaluation(
            (self._case("TRUNCATED", "truncated"),),
            _FakeService({"truncated": self._success(truncated=True)}),
            _FakeExecutor(self.reference),
            self.context,
            trace_recorder=recorder,
        )
        truncated_report = create_report(truncated_run, metadata)
        truncated_markdown = render_markdown_report(truncated_report)
        truncated_trace_id = truncated_run.cases[0].trace_id
        self.assertIn(
            f"| TRUNCATED | evaluation-TRUNCATED | {truncated_trace_id} |",
            truncated_markdown,
        )

        old_report = {
            "metadata": {
                "test_set_hash": "same-test",
                "reference_result_hash": "same-reference",
            },
            "cases": [{"case_id": "PASS", "status": "PASS"}],
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "old.json"
            path.write_text(json.dumps(old_report), encoding="utf-8")
            loaded = load_report(path)

        comparison = compare_baseline(report, loaded)
        self.assertTrue(comparison["comparable"])

    def test_recorder_failure_is_fail_open_and_keeps_business_result(self) -> None:
        class BrokenRecorder:
            def query_trace(self, *args: object, **kwargs: object) -> object:
                raise RuntimeError("trace failure")

        service = _FakeService({"pass": self._success()})
        run = run_evaluation(
            (self._case("BROKEN", "pass"),),
            service,
            _FakeExecutor(self.reference),
            self.context,
            trace_recorder=BrokenRecorder(),  # type: ignore[arg-type]
        )

        self.assertEqual(run.cases[0].status, CaseStatus.PASS)
        self.assertEqual(run.cases[0].request_id, "evaluation-BROKEN")
        self.assertRegex(run.cases[0].trace_id or "", TRACE_ID_RE)
        self.assertEqual(len(service.calls), 1)

    def _case(
        self,
        case_id: str,
        question: str,
        *,
        expected_sql: str | None = None,
    ) -> EvaluationCase:
        return EvaluationCase(
            id=case_id,
            schema_name="mart_sales",
            category="simple",
            question=question,
            description="T4B 测试案例",
            expected_sql=expected_sql or self.sql,
        )

    @staticmethod
    def _success(
        *,
        rows: tuple[tuple[object, ...], ...] = ((1,),),
        truncated: bool = False,
    ) -> QuerySuccess:
        return QuerySuccess(
            request_id="service-request",
            sql="SELECT 1",
            columns=("value",),
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
        )


if __name__ == "__main__":
    unittest.main()
