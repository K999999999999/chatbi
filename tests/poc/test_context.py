"""结构元数据和指标文件的上下文组合测试。"""

from pathlib import Path
import unittest

from src.poc.context import ContextBuilder
from src.poc.semantic import MetricCatalog
from src.poc.structure import StructureCatalog


ROOT = Path(__file__).resolve().parents[2]


class ContextTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        structure = StructureCatalog.from_directory(
            ROOT / "src" / "poc" / "structure" / "generated"
        )
        metrics = MetricCatalog.from_file(
            ROOT / "src" / "poc" / "semantic" / "metrics.json"
        )
        metrics.validate_against_structure(structure)
        cls.builder = ContextBuilder(structure, metrics)

    def test_context_contains_physical_and_semantic_facts(self) -> None:
        context = self.builder.build("查询 2025 年各产品线的销售额")
        prompt = context.render_prompt()
        self.assertIn("mart_sales.fct_sales_order_line", prompt)
        self.assertIn("net_sales_amount_cny", prompt)
        self.assertIn("sales_revenue", prompt)
        self.assertIn("order_status = 'completed'", prompt)
        self.assertNotIn("public.sales_orders", prompt)


if __name__ == "__main__":
    unittest.main()
