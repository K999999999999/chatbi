"""Business Analysis Task Decomposer 测试。"""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.business_analysis.contracts import AnalysisDecompositionContext
from src.business_analysis.decomposer import (
    LangChainAnalysisPlanDecomposer,
    build_analysis_plan_prompt,
)


class AnalysisDecomposerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.context = AnalysisDecompositionContext(
            current_time="2026-09-21T12:00:00+08:00",
            metric_records=({"name": "人民币净销售额", "aliases": ["销售额"]},),
            dimensions=("销售区域", "产品线"),
        )

    def test_prompt_requires_semantic_plan_without_sql(self) -> None:
        prompt = build_analysis_plan_prompt(
            "最近三个月销售额为什么下降",
            self.context,
        )

        self.assertIn('"tasks"', prompt)
        self.assertIn("销售区域", prompt)
        self.assertIn("最多 12 个 Task", prompt)
        self.assertIn("不要输出 SQL", prompt)
        self.assertIn("time_range 格式", prompt)
        self.assertIn('"text": "最近三个月", "granularity": "month"', prompt)
        self.assertIn("metrics 必须保留用户的“利润”表达", prompt)
        self.assertIn("比较多个明确时期时", prompt)
        self.assertIn("先生成趋势 Task，再生成下钻 breakdown Task", prompt)
        self.assertIn("filters 格式", prompt)
        self.assertIn("最近三个月销售额为什么下降", prompt)

    def test_decomposer_parses_one_json_plan(self) -> None:
        model = Mock()
        model.invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "tasks": [
                        {
                            "task_id": "root",
                            "task_type": "baseline",
                            "description": "查询销售额趋势",
                            "metrics": ["销售额"],
                            "dimensions": [],
                            "time_range": None,
                            "filters": [],
                            "depends_on": [],
                            "expected_output": "整体趋势",
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )

        result = LangChainAnalysisPlanDecomposer(model).decompose(
            "最近三个月销售额为什么下降",
            self.context,
        )

        self.assertEqual(result.tasks[0].task_id, "root")
        self.assertEqual(result.tasks[0].metrics, ("销售额",))
        model.invoke.assert_called_once()

    def test_invalid_json_and_provider_failure_are_controlled(self) -> None:
        invalid_model = Mock()
        invalid_model.invoke.return_value = SimpleNamespace(content="not-json")
        with self.assertRaisesRegex(RuntimeError, "合法 JSON"):
            LangChainAnalysisPlanDecomposer(invalid_model).decompose(
                "查询销售额",
                self.context,
            )

        failed_model = Mock()
        failed_model.invoke.side_effect = TimeoutError("provider detail")
        with self.assertRaisesRegex(RuntimeError, "LLM 调用失败"):
            LangChainAnalysisPlanDecomposer(failed_model).decompose(
                "查询销售额",
                self.context,
            )


if __name__ == "__main__":
    unittest.main()
