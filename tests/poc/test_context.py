"""Prompt Builder（提示词构造器）的结构和指标注入测试。"""

from pathlib import Path
import unittest

from src.prompt_builder import PromptBuilder
from src.semantic import MetricCatalog
from src.structure import StructureCatalog


ROOT = Path(__file__).resolve().parents[2]


class ContextTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        structure = StructureCatalog.from_directory(
            ROOT / "src" / "structure" / "generated"
        )
        metrics = MetricCatalog.from_file(
            ROOT / "src" / "semantic" / "metrics.json"
        )
        metrics.validate_against_structure(structure)
        cls.builder = PromptBuilder(structure, metrics)

    def test_context_contains_physical_and_semantic_facts(self) -> None:
        context = self.builder.build("查询 2025 年各产品线的销售额")
        prompt = context.render_prompt()
        system_message, user_prompt = context.render_messages()
        self.assertIn("mart_sales.fct_sales_order_line", prompt)
        self.assertIn("net_sales_amount_cny", prompt)
        self.assertIn("sales_revenue", prompt)
        self.assertIn("order_status = 'completed'", prompt)
        self.assertNotIn("public.sales_orders", prompt)
        self.assertIn("你是 ChatBI 的专业 PostgreSQL SQL 生成助手", system_message)
        self.assertEqual(prompt, user_prompt)
        self.assertIn("UNSUPPORTED", prompt)


if __name__ == "__main__":
    unittest.main()
