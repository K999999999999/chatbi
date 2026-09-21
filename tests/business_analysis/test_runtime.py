"""Business Analysis 生产语义上下文装配测试。"""

import unittest

from src.business_analysis.runtime import load_analysis_context


class AnalysisRuntimeTest(unittest.TestCase):
    def test_default_context_uses_explicit_metric_and_dimension_facts(self) -> None:
        context = load_analysis_context()

        self.assertTrue(context.metric_records)
        self.assertIn("人民币净销售额", {record["name"] for record in context.metric_records})
        self.assertIn("销售区域", context.dimensions)
        self.assertNotIn("sales_region_name", context.dimensions)
        self.assertTrue(context.current_time)


if __name__ == "__main__":
    unittest.main()
