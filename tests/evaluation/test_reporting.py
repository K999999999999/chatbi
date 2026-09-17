"""Evaluation（评测）报告、指纹和 Baseline（基线）比较测试。"""

import json
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from src.evaluation.runner import (
    CaseEvaluation,
    CaseStatus,
    EvaluationRun,
    EvaluationSummary,
)
from src.online_query.contracts import QueryData


class EvaluationReportingTest(unittest.TestCase):
    def test_collects_reproducible_metadata_without_secrets_or_endpoint(self) -> None:
        from src.evaluation.reporting import collect_run_metadata

        run = self._run((CaseStatus.PASS,))
        environ = {
            "LLM_API_KEY": "secret-key",
            "POSTGRES_APP_PASSWORD": "secret-password",
            "LLM_BASE_URL": "https://internal.example/v1",
            "LLM_MODEL": "test-model",
            "LLM_TEMPERATURE": "0.1",
            "LLM_MAX_TOKENS": "1200",
        }
        with TemporaryDirectory() as directory:
            root = Path(directory)
            test_set = root / "cases.json"
            test_set.write_text("[]", encoding="utf-8")
            context_file = root / "metrics.json"
            context_file.write_text('[{"name":"销售额"}]', encoding="utf-8")

            metadata = collect_run_metadata(
                run,
                git_commit="abcdef1234567890",
                git_dirty=False,
                environ=environ,
                test_set_path=test_set,
                context_paths={"metrics": context_file},
                now=datetime(2026, 8, 31, 12, 0, 0, tzinfo=UTC),
            )

        encoded = json.dumps(metadata.to_dict(), ensure_ascii=False)
        self.assertEqual(metadata.run_id, "20260831T120000Z-abcdef1")
        self.assertEqual(metadata.git_commit, "abcdef1234567890")
        self.assertEqual(metadata.model, "test-model")
        self.assertEqual(metadata.temperature, 0.1)
        self.assertEqual(metadata.max_tokens, 1200)
        self.assertNotIn("internal.example", encoded)
        self.assertNotIn("secret-key", encoded)
        self.assertNotIn("secret-password", encoded)
        self.assertEqual(len(metadata.test_set_hash), 64)
        self.assertEqual(len(metadata.context_hash), 64)
        self.assertEqual(len(metadata.reference_result_hash), 64)

    def test_writes_and_loads_json_report(self) -> None:
        from src.evaluation.reporting import (
            collect_run_metadata,
            create_report,
            load_report,
            write_report,
        )

        run = self._run((CaseStatus.PASS, CaseStatus.FAIL))
        with TemporaryDirectory() as directory:
            root = Path(directory)
            test_set = root / "cases.json"
            test_set.write_text("[]", encoding="utf-8")
            context_file = root / "context.json"
            context_file.write_text("[]", encoding="utf-8")
            metadata = collect_run_metadata(
                run,
                git_commit="abcdef1",
                git_dirty=True,
                environ={"LLM_MODEL": "model-a"},
                test_set_path=test_set,
                context_paths={"context": context_file},
                now=datetime(2026, 8, 31, 12, 0, 0, tzinfo=UTC),
            )
            report = create_report(run, metadata)
            output = root / "reports" / "baseline.json"

            write_report(report, output)
            loaded = load_report(output)

        self.assertEqual(loaded, report)
        self.assertEqual(loaded["summary"]["execution_accuracy"], 0.5)
        self.assertEqual(len(loaded["cases"]), 2)
        self.assertIsNone(loaded["baseline_comparison"])

    def test_renders_human_readable_summary_without_baseline(self) -> None:
        from src.evaluation.reporting import create_report, render_markdown_report

        run = self._run(
            (CaseStatus.PASS, CaseStatus.FAIL, CaseStatus.INVALID_CASE)
        )
        report = create_report(run, self._metadata())

        markdown = render_markdown_report(report)

        self.assertIn("## 总体结论", markdown)
        self.assertIn("**FAIL**", markdown)
        self.assertIn(
            "本次共评测 3 条：成功 1 条，失败 1 条，无效 1 条；"
            "有效案例执行准确率 50.00%。",
            markdown,
        )
        self.assertIn("| C2 | simple | FAIL | 未说明 | 失败 |", markdown)
        self.assertIn("| C3 | simple | INVALID_CASE | 未说明 | 失败 |", markdown)
        self.assertIn("本次未执行自动基线比较", markdown)

    def test_report_exposes_query_understanding_failure_stage(self) -> None:
        from src.evaluation.reporting import create_report, render_markdown_report

        run = self._run((CaseStatus.FAIL,))
        run = replace(
            run,
            cases=(
                replace(
                    run.cases[0],
                    failure_stage="query_understanding",
                    internal_reason="QUERY_TYPE_UNKNOWN",
                ),
            ),
        )

        report = create_report(run, self._metadata())
        markdown = render_markdown_report(report)

        self.assertEqual(
            report["summary"]["failure_stage_counts"],
            {"query_understanding": 1},
        )
        self.assertEqual(
            report["cases"][0]["internal_reason"],
            "QUERY_TYPE_UNKNOWN",
        )
        self.assertIn(
            "| C1 | simple | FAIL | query_understanding | 失败 |",
            markdown,
        )

    def test_renders_regression_and_improvement_summary(self) -> None:
        from src.evaluation.reporting import create_report, render_markdown_report

        baseline = self._report(
            test_hash="same-test",
            reference_hash="same-reference",
            statuses={"C1": "PASS", "C2": "FAIL", "C3": "PASS"},
        )
        report = create_report(
            self._run((CaseStatus.FAIL, CaseStatus.PASS, CaseStatus.PASS)),
            self._metadata(),
            baseline,
        )

        markdown = render_markdown_report(report)

        self.assertIn("能力回退 1 条：C1", markdown)
        self.assertIn("能力改善 1 条：C2", markdown)
        self.assertIn("状态未变化 1 条", markdown)

    def test_compares_regressions_and_improvements(self) -> None:
        from src.evaluation.reporting import compare_baseline

        baseline = self._report(
            test_hash="same-test",
            reference_hash="same-reference",
            statuses={"A": "PASS", "B": "FAIL", "C": "PASS"},
        )
        current = self._report(
            test_hash="same-test",
            reference_hash="same-reference",
            statuses={"A": "FAIL", "B": "PASS", "C": "PASS"},
        )

        comparison = compare_baseline(current, baseline)

        self.assertTrue(comparison["comparable"])
        self.assertEqual(comparison["regressions"], ["A"])
        self.assertEqual(comparison["improvements"], ["B"])
        self.assertEqual(comparison["unchanged"], ["C"])

    def test_refuses_regression_claim_when_inputs_are_incomparable(self) -> None:
        from src.evaluation.reporting import compare_baseline

        baseline = self._report(
            test_hash="test-a",
            reference_hash="reference-a",
            statuses={"A": "PASS"},
        )
        changed_test = self._report(
            test_hash="test-b",
            reference_hash="reference-a",
            statuses={"A": "FAIL"},
        )
        changed_database = self._report(
            test_hash="test-a",
            reference_hash="reference-b",
            statuses={"A": "FAIL"},
        )

        test_comparison = compare_baseline(changed_test, baseline)
        database_comparison = compare_baseline(changed_database, baseline)

        self.assertFalse(test_comparison["comparable"])
        self.assertFalse(database_comparison["comparable"])
        self.assertEqual(test_comparison["regressions"], [])
        self.assertEqual(database_comparison["regressions"], [])

    def test_rejects_invalid_report_file(self) -> None:
        from src.evaluation.reporting import ReportingError, load_report

        with TemporaryDirectory() as directory:
            root = Path(directory)
            invalid_json = root / "invalid.json"
            invalid_json.write_text("{", encoding="utf-8")
            with self.assertRaises(ReportingError):
                load_report(invalid_json)

            non_object = root / "array.json"
            non_object.write_text("[]", encoding="utf-8")
            with self.assertRaises(ReportingError):
                load_report(non_object)

    @staticmethod
    def _run(statuses: tuple[CaseStatus, ...]) -> EvaluationRun:
        cases = tuple(
            CaseEvaluation(
                case_id=f"C{index}",
                category="simple",
                status=status,
                generated_sql="SELECT 1" if status != CaseStatus.INVALID_CASE else None,
                query_error_code=None,
                failure_reason=None if status == CaseStatus.PASS else "失败",
                duration_ms=10,
            )
            for index, status in enumerate(statuses, 1)
        )
        valid = [case for case in cases if case.status != CaseStatus.INVALID_CASE]
        passed = sum(case.status == CaseStatus.PASS for case in valid)
        summary = EvaluationSummary(
            total_cases=len(cases),
            valid_cases=len(valid),
            passed=passed,
            failed=len(valid) - passed,
            invalid_cases=len(cases) - len(valid),
            execution_accuracy=passed / len(valid) if valid else None,
            category_accuracy={
                "simple": passed / len(valid) if valid else None,
            },
        )
        references = {
            case.case_id: QueryData(
                columns=("value",),
                rows=((Decimal(str(index)),),),
                truncated=False,
            )
            for index, case in enumerate(cases, 1)
            if case.status != CaseStatus.INVALID_CASE
        }
        return EvaluationRun(
            cases=cases,
            summary=summary,
            reference_results=references,
        )

    @staticmethod
    def _metadata():
        from src.evaluation.reporting import RunMetadata

        return RunMetadata(
            run_id="20260831T120000Z-abcdef1",
            created_at="2026-08-31T12:00:00Z",
            git_commit="abcdef1234567890",
            git_dirty=False,
            model="test-model",
            temperature=0.1,
            max_tokens=1200,
            model_endpoint_hash="endpoint",
            test_set_hash="same-test",
            context_hash="context",
            reference_result_hash="same-reference",
        )

    @staticmethod
    def _report(
        *,
        test_hash: str,
        reference_hash: str,
        statuses: dict[str, str],
    ) -> dict[str, object]:
        return {
            "metadata": {
                "test_set_hash": test_hash,
                "reference_result_hash": reference_hash,
            },
            "cases": [
                {"case_id": case_id, "status": status}
                for case_id, status in statuses.items()
            ],
        }


if __name__ == "__main__":
    unittest.main()
