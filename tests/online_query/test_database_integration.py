"""使用本地 PostgreSQL 的 Database Adapter（数据库适配器）集成测试。"""

import os
import unittest

from src.online_query.contracts import ValidatedSQL
from src.online_query.database import DatabaseError, PsycopgQueryExecutor


@unittest.skipUnless(
    os.environ.get("RUN_DATABASE_TESTS") == "1",
    "需要显式启用本地 PostgreSQL 集成测试",
)
class DatabaseIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.executor = PsycopgQueryExecutor.from_env()

    def test_uses_chatbi_app_read_only_transaction_and_ten_second_timeout(
        self,
    ) -> None:
        result = self.executor.execute(
            ValidatedSQL(
                "SELECT current_user, "
                "current_setting('transaction_read_only'), "
                "current_setting('statement_timeout') "
                "FROM mart_sales.fct_sales_order_line LIMIT 1"
            )
        )

        self.assertEqual(result.rows[0], ("chatbi_app", "on", "10s"))

    def test_empty_result_is_success(self) -> None:
        result = self.executor.execute(
            ValidatedSQL(
                "SELECT order_id FROM mart_sales.fct_sales_order_line WHERE false"
            )
        )

        self.assertEqual(result.rows, ())
        self.assertFalse(result.truncated)

    def test_real_query_is_truncated_to_100_rows(self) -> None:
        result = self.executor.execute(
            ValidatedSQL(
                "SELECT order_id FROM mart_sales.fct_sales_order_line ORDER BY order_id"
            )
        )

        self.assertEqual(len(result.rows), 100)
        self.assertTrue(result.truncated)

    def test_read_only_transaction_blocks_write_even_after_guard(self) -> None:
        with self.assertRaises(DatabaseError):
            self.executor.execute(
                ValidatedSQL("DELETE FROM mart_sales.fct_sales_order_line WHERE false")
            )


if __name__ == "__main__":
    unittest.main()
