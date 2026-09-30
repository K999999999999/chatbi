"""经营分析拆解与总结 Judge 的输入和 Contract 测试。"""

import json
import unittest
from pathlib import Path

from src.business_analysis.application import BusinessAnalysisSuccess
from src.business_analysis.reporting import BusinessAnalysisReport
from evaluation.suites.business_analysis.business_analysis_evaluation import (
    load_business_analysis_cases,
)
from evaluation.suites.business_analysis.business_analysis_judge import (
    LangChainBusinessAnalysisJudge,
)


class BusinessAnalysisJudgeTest(unittest.TestCase):
    def test_plan_and_summary_use_separate_prompts(self) -> None:
        model = _FakeModel({"passed": True, "reason": "覆盖完整。"})
        judge = LangChainBusinessAnalysisJudge(model)
        case = _cases()[0]

        plan = judge.evaluate_plan(case, _success())
        plan_prompt = model.prompts[-1]
        summary = judge.evaluate_summary(case, _success())
        summary_prompt = model.prompts[-1]

        self.assertTrue(plan.passed)
        self.assertTrue(summary.passed)
        self.assertNotEqual(plan_prompt, summary_prompt)
        self.assertIn('"expected_task_count": 4', plan_prompt)
        self.assertIn('"expected_tasks"', summary_prompt)
        self.assertIn('"report"', summary_prompt)

    def test_invalid_judge_output_fails_closed(self) -> None:
        model = _FakeModel({"passed": "yes", "reason": "无效"})
        with self.assertRaises(ValueError):
            LangChainBusinessAnalysisJudge(model).evaluate_plan(_cases()[0], _success())


class _FakeModel:
    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        self.prompts: list[str] = []

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        return type(
            "Response", (), {"content": json.dumps(self.result, ensure_ascii=False)}
        )()


def _cases():
    root = Path(__file__).resolve().parents[3]
    return load_business_analysis_cases(
        root / "evaluation/suites/business_analysis/cases.json"
    )


def _success() -> BusinessAnalysisSuccess:
    return BusinessAnalysisSuccess(
        request_id="judge-test",
        report=BusinessAnalysisReport(
            title="报告",
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
