"""SQL Guard 安全边界测试。"""

from pathlib import Path
import unittest

from src.poc.sql_guard import SqlGuard, SqlValidationError
from src.poc.structure import StructureCatalog


ROOT = Path(__file__).resolve().parents[2]


class SqlGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        structure = StructureCatalog.from_directory(
            ROOT / "src" / "poc" / "structure" / "generated"
        )
        cls.guard = SqlGuard(structure)

    def test_generated_select_passes(self) -> None:
        sql = """SELECT SUM(f.net_sales_amount_cny) AS sales_revenue
FROM mart_sales.fct_sales_order_line AS f
WHERE f.order_status = 'completed'"""
        self.assertEqual(sql, self.guard.validate(sql).sql)

    def test_write_statement_is_rejected(self) -> None:
        with self.assertRaisesRegex(SqlValidationError, "只允许 SELECT"):
            self.guard.validate("DELETE FROM mart_sales.fct_sales_order_line")

    def test_public_schema_is_rejected(self) -> None:
        with self.assertRaisesRegex(SqlValidationError, "只能访问 mart_sales"):
            self.guard.validate("SELECT COUNT(*) FROM public.sales_orders")

    def test_unknown_table_is_rejected(self) -> None:
        with self.assertRaisesRegex(SqlValidationError, "未知表"):
            self.guard.validate("SELECT COUNT(*) FROM mart_sales.not_a_table")

    def test_unknown_column_is_rejected(self) -> None:
        with self.assertRaisesRegex(SqlValidationError, "未知字段"):
            self.guard.validate(
                "SELECT f.not_a_column FROM mart_sales.fct_sales_order_line AS f"
            )

    def test_multiple_statements_are_rejected(self) -> None:
        with self.assertRaisesRegex(SqlValidationError, "一条语句"):
            self.guard.validate(
                "SELECT COUNT(*) FROM mart_sales.fct_sales_order_line; "
                "DELETE FROM mart_sales.fct_sales_order_line"
            )

    def test_dangerous_system_function_is_rejected(self) -> None:
        with self.assertRaisesRegex(SqlValidationError, "系统函数"):
            self.guard.validate(
                "SELECT pg_sleep(1) FROM mart_sales.fct_sales_order_line"
            )


if __name__ == "__main__":
    unittest.main()
