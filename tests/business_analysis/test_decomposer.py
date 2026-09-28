"""Business Analysis 请求语义提取测试。"""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.business_analysis.contracts import AnalysisDecompositionContext
from src.business_analysis.decomposer import (
    LangChainAnalysisRequestExtractor,
    build_analysis_request_prompt,
)


class AnalysisDecomposerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.context = AnalysisDecompositionContext(
            current_time="2026-09-21T12:00:00+08:00",
            metric_records=(
                {"name": "人民币净销售额", "aliases": ["销售额"]},
                {"name": "人民币毛利", "aliases": ["毛利"]},
            ),
            dimensions=("销售区域", "产品线"),
        )

    def test_prompt_only_extracts_metric_and_periods(self) -> None:
        prompt = build_analysis_request_prompt(
            "2025年3月毛利为什么比2月下降",
            self.context,
        )

        self.assertIn('"metric_text"', prompt)
        self.assertIn('"current_period"', prompt)
        self.assertIn('"comparison_period"', prompt)
        self.assertIn("不得把“利润”改写成“毛利”", prompt)
        self.assertIn("按上下文可唯一确定年份时", prompt)
        self.assertIn("不输出 Task、维度", prompt)
        self.assertNotIn("销售区域", prompt)
        self.assertNotIn('"tasks"', prompt)
        self.assertIn("2025年3月毛利为什么比2月下降", prompt)

    def test_decomposer_parses_metric_and_two_periods(self) -> None:
        model = Mock()
        model.invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "metric_text": "毛利",
                    "current_period": {
                        "text": "2025年3月",
                        "granularity": "month",
                    },
                    "comparison_period": {
                        "text": "2025年2月",
                        "granularity": "month",
                    },
                },
                ensure_ascii=False,
            )
        )

        result = LangChainAnalysisRequestExtractor(model).decompose(
            "2025年3月毛利为什么比2月下降",
            self.context,
        )

        self.assertEqual(result.metric_text, "毛利")
        self.assertEqual(result.current_period.text, "2025年3月")
        self.assertEqual(result.comparison_period.text, "2025年2月")
        model.invoke.assert_called_once()

    def test_invalid_json_and_provider_failure_are_controlled(self) -> None:
        invalid_model = Mock()
        invalid_model.invoke.return_value = SimpleNamespace(content="not-json")
        with self.assertRaisesRegex(RuntimeError, "合法 JSON"):
            LangChainAnalysisRequestExtractor(invalid_model).decompose(
                "2025年3月销售额比2月变化",
                self.context,
            )

        failed_model = Mock()
        failed_model.invoke.side_effect = TimeoutError("provider detail")
        with self.assertRaisesRegex(RuntimeError, "LLM 调用失败"):
            LangChainAnalysisRequestExtractor(failed_model).decompose(
                "2025年3月销售额比2月变化",
                self.context,
            )


if __name__ == "__main__":
    unittest.main()
