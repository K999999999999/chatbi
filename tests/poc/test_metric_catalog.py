"""指标语义层契约测试。"""

from pathlib import Path
import unittest

from src.poc.semantic import MetricCatalog
from src.poc.structure import StructureCatalog


ROOT = Path(__file__).resolve().parents[2]


class MetricCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.structure = StructureCatalog.from_directory(
            ROOT / "src" / "poc" / "structure" / "generated"
        )
        cls.catalog = MetricCatalog.from_file(
            ROOT / "src" / "poc" / "semantic" / "metrics.json"
        )
        cls.catalog.validate_against_structure(cls.structure)

    def test_five_metrics_are_loaded(self) -> None:
        self.assertEqual(
            {
                "sales_quantity",
                "sales_revenue",
                "sales_cost",
                "gross_profit",
                "gross_margin",
            },
            {metric.metric_code for metric in self.catalog.metrics},
        )

    def test_metric_matching_prefers_longer_non_overlapping_terms(self) -> None:
        self.assertEqual(
            ("gross_margin",),
            tuple(
                metric.metric_code
                for metric in self.catalog.match_question("查询各区域的毛利率")
            ),
        )
        self.assertEqual(
            ("gross_profit", "gross_margin"),
            tuple(
                metric.metric_code
                for metric in self.catalog.match_question("查询毛利和毛利率")
            ),
        )

    def test_unsupported_net_profit_is_not_invented(self) -> None:
        with self.assertRaisesRegex(ValueError, "未识别到"):
            self.catalog.require_single("查询 2025 年的净利润")


if __name__ == "__main__":
    unittest.main()
