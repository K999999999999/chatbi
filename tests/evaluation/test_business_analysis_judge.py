"""经营分析总结 Judge 的输入和 Contract 测试。"""

import json
import unittest
from decimal import Decimal

from src.business_analysis.application import BusinessAnalysisSuccess
from src.business_analysis.attribution import BusinessAnalysisAttribution
from src.business_analysis.execution import TaskResult, TaskStatus
from src.business_analysis.reporting import BusinessAnalysisReport
from src.evaluation.business_analysis_judge import LangChainBusinessAnalysisJudge


class BusinessAnalysisJudgeTest(unittest.TestCase):
    def test_judge_checks_report_against_program_owned_attribution(self) -> None:
        model = _FakeModel({"passed": True, "reason": "方向和产品因素均有依据。"})

        result = LangChainBusinessAnalysisJudge(model).evaluate(
            "2025年3月毛利为什么比2月下降？",
            _success(),
        )

        self.assertTrue(result.passed)
        self.assertIn('"direction": "increase"', model.prompt)
        self.assertIn("不要计算或重算任何金额", model.prompt)
        self.assertIn("不得把数据关联误说成数据库未证明的经营因果", model.prompt)

    def test_invalid_judge_output_fails_closed(self) -> None:
        model = _FakeModel({"passed": "yes", "reason": "不合法"})

        with self.assertRaises(ValueError):
            LangChainBusinessAnalysisJudge(model).evaluate("分析", _success())


class _FakeModel:
    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        self.prompt = ""

    def invoke(self, prompt: str):
        self.prompt = prompt
        return type(
            "Response",
            (),
            {"content": json.dumps(self.result, ensure_ascii=False)},
        )()


def _success() -> BusinessAnalysisSuccess:
    attribution = BusinessAnalysisAttribution(
        metric_name="人民币毛利",
        current_period="2025年3月",
        comparison_period="2025年2月",
        comparison_value=Decimal("100"),
        current_value=Decimal("120"),
        total_change=Decimal("20"),
        products=(),
        top_products=(),
    )
    return BusinessAnalysisSuccess(
        request_id="judge-test",
        report=BusinessAnalysisReport(
            title="毛利分析",
            executive_summary="毛利上升。",
            key_findings=("毛利增加。",),
            trend_judgment="整体上升",
            root_causes=(),
            action_suggestions=(),
            evidence_task_ids=(),
            incomplete_tasks=(),
            attribution=attribution,
        ),
        task_results=(
            TaskResult(
                task_id="current-overall",
                status=TaskStatus.COMPLETED,
                columns=("value",),
                rows=((120,),),
                row_count=1,
            ),
        ),
        attribution=attribution,
    )
