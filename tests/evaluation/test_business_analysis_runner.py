"""经营分析评测 Runner 测试。"""

import unittest
from pathlib import Path

from src.authorization import AuthContext
from src.business_analysis.application import BusinessAnalysisSuccess
from src.business_analysis.reporting import BusinessAnalysisReport
from src.evaluation.business_analysis_evaluation import load_business_analysis_cases
from src.evaluation.business_analysis_runner import (
    BusinessAnalysisCaseStatus,
    JudgeResult,
    run_business_analysis_evaluation,
)
from src.online_query.contracts import QueryErrorCode, QueryFailure


class BusinessAnalysisRunnerTest(unittest.TestCase):
    def test_plan_and_summary_are_judged_independently(self) -> None:
        case = self._cases()[0]
        judge = _FakeJudge(plan=False, summary=True)
        run = run_business_analysis_evaluation(
            [case],
            _FakeApplication(_success()),
            AuthContext(subject_id="eval", identity_provider="test"),
            judge=judge,
        )
        evaluation = run.cases[0]
        self.assertEqual(evaluation.status, BusinessAnalysisCaseStatus.FAIL)
        self.assertFalse(evaluation.plan_passed)
        self.assertTrue(evaluation.summary_passed)
        self.assertEqual(judge.calls, ["plan", "summary"])
        self.assertEqual(run.summary.plan_accuracy, 0.0)
        self.assertEqual(run.summary.summary_accuracy, 1.0)

    def test_clarification_and_refusal_are_checked_by_error_code(self) -> None:
        cases = self._cases()
        examples = (
            ("clarification_required", QueryErrorCode.CLARIFICATION_REQUIRED),
            ("cannot_answer", QueryErrorCode.CANNOT_ANSWER),
        )
        for expected_outcome, error_code in examples:
            with self.subTest(expected_outcome=expected_outcome):
                case = next(
                    item for item in cases if item.expected_outcome == expected_outcome
                )
                result = QueryFailure(
                    request_id="test",
                    error_code=error_code,
                    error_message="符合案例预期",
                )
                run = run_business_analysis_evaluation(
                    [case],
                    _FakeApplication(result),
                    AuthContext(subject_id="eval", identity_provider="test"),
                    judge=None,
                )
                self.assertEqual(run.cases[0].status, BusinessAnalysisCaseStatus.PASS)
                self.assertIsNone(run.cases[0].summary_passed)
                self.assertIsNone(run.cases[0].plan_passed)

    @staticmethod
    def _cases():
        root = Path(__file__).resolve().parents[2]
        return load_business_analysis_cases(
            root / "src/evaluation/business_analysis_cases.json"
        )


class _FakeApplication:
    def __init__(self, result):
        self.result = result

    def analyze(self, question, *, request_id, auth_context, analysis_run_id=None):
        del question, request_id, auth_context, analysis_run_id
        return self.result


class _FakeJudge:
    def __init__(self, *, plan: bool, summary: bool) -> None:
        self.results = {"plan": plan, "summary": summary}
        self.calls: list[str] = []

    def evaluate_plan(self, case, result):
        del case, result
        self.calls.append("plan")
        return JudgeResult(self.results["plan"], "拆解依据")

    def evaluate_summary(self, case, result):
        del case, result
        self.calls.append("summary")
        return JudgeResult(self.results["summary"], "总结依据")


def _success() -> BusinessAnalysisSuccess:
    return BusinessAnalysisSuccess(
        request_id="eval-test",
        report=BusinessAnalysisReport(
            title="经营分析",
            executive_summary="摘要",
            key_findings=(),
            trend_judgment="变化",
            root_causes=(),
            action_suggestions=(),
            evidence_task_ids=(),
            incomplete_tasks=(),
        ),
        task_results=(),
    )


if __name__ == "__main__":
    unittest.main()
