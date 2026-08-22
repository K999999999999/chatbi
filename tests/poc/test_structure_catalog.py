"""结构目录的 POC 契约测试。"""

from pathlib import Path
import unittest

from src.structure import StructureCatalog


ROOT = Path(__file__).resolve().parents[2]


class StructureCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = StructureCatalog.from_directory(
            ROOT / "src" / "structure" / "generated"
        )

    def test_current_mart_sales_snapshot_is_loaded(self) -> None:
        self.assertEqual("mart_sales", self.catalog.schema_name)
        self.assertEqual(7, len(self.catalog.tables))
        self.assertEqual(69, len(self.catalog.columns))
        self.assertEqual(9, len(self.catalog.relationships["foreign_keys"]))
        self.assertNotIn("public", self.catalog.render_prompt())

    def test_fact_and_business_columns_are_available(self) -> None:
        self.assertTrue(
            self.catalog.has_column(
                "fct_sales_order_line", "net_sales_amount_cny"
            )
        )
        self.assertTrue(
            self.catalog.has_column(
                "fct_sales_order_line", "sales_cost_amount_cny"
            )
        )
        self.assertTrue(
            self.catalog.has_column("dim_customer", "customer_region")
        )
        self.assertTrue(
            self.catalog.has_column("dim_product", "product_line")
        )


if __name__ == "__main__":
    unittest.main()
