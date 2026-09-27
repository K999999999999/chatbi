"""利润指标口径歧义规则测试。"""

import unittest

from src.semantic.metric_ambiguity import requires_metric_clarification


class MetricAmbiguityTest(unittest.TestCase):
    def test_unqualified_profit_requires_clarification(self) -> None:
        self.assertTrue(requires_metric_clarification("帮我查一下利润。"))

    def test_explicit_profit_metric_does_not_require_clarification(self) -> None:
        for question in ("查询毛利", "查询毛利率", "查询净利润"):
            with self.subTest(question=question):
                self.assertFalse(requires_metric_clarification(question))

    def test_non_profit_metric_does_not_require_clarification(self) -> None:
        self.assertFalse(requires_metric_clarification("查询人民币销售额"))


if __name__ == "__main__":
    unittest.main()
