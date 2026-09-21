"""经营分析评估报告测试。"""

import unittest

from src.evaluation.business_analysis_reporting import (
    create_business_analysis_report,
    render_business_analysis_markdown,
)
from src.evaluation.business_analysis_runner import (
    BusinessAnalysisCaseEvaluation,
    BusinessAnalysisCaseStatus,
    BusinessAnalysisEvaluationRun,
    BusinessAnalysisEvaluationSummary,
)
from src.evaluation.reporting import RunMetadata


class BusinessAnalysisReportingTest(unittest.TestCase):
    def test_report_contains_layered_scores_and_case_evidence(self) -> None:
        report = create_business_analysis_report(_run(), _metadata())

        self.assertEqual(report["summary"]["plan_accuracy"], 1.0)
        self.assertEqual(report["summary"]["task_execution_accuracy"], 1.0)
        self.assertEqual(report["summary"]["report_grounded_accuracy"], 1.0)
        self.assertEqual(report["summary"]["end_to_end_accuracy"], 1.0)
        self.assertEqual(report["cases"][0]["status"], "PASS")
        markdown = render_business_analysis_markdown(report)
        self.assertIn("经营分析 Evaluation（评估）", markdown)
        self.assertIn("端到端案例准确率", markdown)
        self.assertIn("CASE-1", markdown)

    def test_report_records_baseline_regression(self) -> None:
        baseline = create_business_analysis_report(_run(), _metadata())
        current = create_business_analysis_report(
            _run(status=BusinessAnalysisCaseStatus.FAIL),
            _metadata(),
            baseline,
        )

        comparison = current["baseline_comparison"]
        self.assertTrue(comparison["comparable"])
        self.assertEqual(comparison["regressions"], ["CASE-1"])


def _run(
    *, status: BusinessAnalysisCaseStatus = BusinessAnalysisCaseStatus.PASS
) -> BusinessAnalysisEvaluationRun:
    passed = status is BusinessAnalysisCaseStatus.PASS
    case = BusinessAnalysisCaseEvaluation(
        case_id="CASE-1",
        status=status,
        plan_passed=passed,
        task_passed=passed,
        report_passed=passed,
        failure_reason=None if passed else "失败",
        reason_code=None if passed else "TEST_FAILURE",
    )
    summary = BusinessAnalysisEvaluationSummary(
        total_cases=1,
        valid_cases=1,
        passed=1 if passed else 0,
        failed=0 if passed else 1,
        invalid_cases=0,
        plan_accuracy=1.0 if passed else 0.0,
        task_execution_accuracy=1.0 if passed else 0.0,
        report_grounded_accuracy=1.0 if passed else 0.0,
        end_to_end_accuracy=1.0 if passed else 0.0,
    )
    return BusinessAnalysisEvaluationRun(
        cases=(case,),
        summary=summary,
        reference_results={},
    )


def _metadata() -> RunMetadata:
    return RunMetadata(
        run_id="20260922T000000Z-abcdef1",
        created_at="2026-09-22T00:00:00Z",
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


if __name__ == "__main__":
    unittest.main()
