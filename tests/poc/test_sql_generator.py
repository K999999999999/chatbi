"""确定性 SQL 基线生成测试。"""

from pathlib import Path
import unittest

from src.poc.context import ContextBuilder
from src.poc.semantic import MetricCatalog
from src.poc.sql_generator import RuleBasedSqlGenerator, SqlGenerationError
from src.poc.structure import StructureCatalog


ROOT = Path(__file__).resolve().parents[2]


class RuleBasedSqlGeneratorTest(unittest.TestCase):
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
        cls.generator = RuleBasedSqlGenerator()

    def test_year_revenue_is_aggregated_not_grouped_by_day(self) -> None:
        context = self.builder.build("查询 2025 年的销售额")
        sql = self.generator.generate(context)
        self.assertIn("SUM(f.net_sales_amount_cny) AS sales_revenue", sql)
        self.assertIn("d.full_date >= DATE '2025-01-01'", sql)
        self.assertNotIn("GROUP BY", sql)

    def test_dimension_query_uses_surrogate_key_join(self) -> None:
        context = self.builder.build("查询 2025 年各产品线的毛利")
        sql = self.generator.generate(context)
        self.assertIn(
            "f.product_key = p.product_key",
            sql,
        )
        self.assertIn("GROUP BY", sql)
        self.assertIn("SUM(f.net_sales_amount_cny) - SUM(f.sales_cost_amount_cny)", sql)

    def test_relative_date_is_rejected_by_deterministic_baseline(self) -> None:
        context = self.builder.build("查询最近三个月的销售额")
        with self.assertRaisesRegex(SqlGenerationError, "明确年份"):
            self.generator.generate(context)


if __name__ == "__main__":
    unittest.main()
