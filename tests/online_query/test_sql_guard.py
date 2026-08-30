"""SQL Guard（SQL 安全校验）测试。"""

import json
from pathlib import Path
import unittest

from src.online_query.contracts import QueryContext
from src.online_query.context import load_query_context
from src.online_query.sql_guard import SQLRejectedError, validate_sql


class SQLGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.context = QueryContext(
            prompt_context="{}",
            allowed_tables=frozenset(
                {
                    "mart_sales.fct_sales_order_line",
                    "mart_sales.dim_customer",
                }
            ),
            allowed_columns={
                "mart_sales.fct_sales_order_line": frozenset(
                    {
                        "order_id",
                        "customer_key",
                        "net_sales_amount_cny",
                        "order_status",
                    }
                ),
                "mart_sales.dim_customer": frozenset(
                    {"customer_key", "customer_name"}
                ),
            },
        )

    def test_valid_select_passes_without_rewriting(self) -> None:
        sql = (
            "SELECT f.order_id, SUM(f.net_sales_amount_cny) AS revenue "
            "FROM mart_sales.fct_sales_order_line AS f "
            "WHERE f.order_status = 'completed' "
            "GROUP BY f.order_id ORDER BY revenue DESC;"
        )

        validated = validate_sql(sql, self.context)

        self.assertEqual(validated.sql, sql)

    def test_cte_join_and_output_alias_pass(self) -> None:
        sql = """
WITH sales AS (
    SELECT customer_key, SUM(net_sales_amount_cny) AS revenue
    FROM mart_sales.fct_sales_order_line
    GROUP BY customer_key
)
SELECT c.customer_name, s.revenue
FROM sales AS s
JOIN mart_sales.dim_customer AS c
  ON c.customer_key = s.customer_key
ORDER BY s.revenue DESC
""".strip()

        validated = validate_sql(sql, self.context)

        self.assertEqual(validated.sql, sql)

    def test_all_metric_sql_templates_pass(self) -> None:
        root = Path(__file__).resolve().parents[2]
        metrics = json.loads(
            (root / "src" / "semantic" / "metrics.json").read_text(
                encoding="utf-8"
            )
        )
        context = load_query_context()

        for metric in metrics:
            with self.subTest(metric=metric["name"]):
                validated = validate_sql(metric["sql_template"], context)
                self.assertEqual(validated.sql, metric["sql_template"])

    def test_rejects_empty_non_sql_and_multiple_statements(self) -> None:
        candidates = (
            "",
            "CANNOT_ANSWER",
            "```sql\nSELECT * FROM mart_sales.fct_sales_order_line\n```",
            "SELECT * FROM mart_sales.fct_sales_order_line; SELECT 1;",
        )

        for sql in candidates:
            with self.subTest(sql=sql):
                with self.assertRaises(SQLRejectedError):
                    validate_sql(sql, self.context)

    def test_rejects_non_select_statements(self) -> None:
        candidates = (
            "INSERT INTO mart_sales.fct_sales_order_line (order_id) VALUES ('x')",
            "UPDATE mart_sales.fct_sales_order_line SET order_status = 'x'",
            "DELETE FROM mart_sales.fct_sales_order_line",
            "DROP TABLE mart_sales.fct_sales_order_line",
            "ALTER TABLE mart_sales.fct_sales_order_line ADD COLUMN x int",
            "TRUNCATE mart_sales.fct_sales_order_line",
            "COPY mart_sales.fct_sales_order_line TO STDOUT",
        )

        for sql in candidates:
            with self.subTest(sql=sql):
                with self.assertRaises(SQLRejectedError):
                    validate_sql(sql, self.context)

    def test_rejects_write_hidden_inside_cte(self) -> None:
        sql = """
WITH changed AS (
    DELETE FROM mart_sales.fct_sales_order_line RETURNING order_id
)
SELECT order_id FROM changed
"""

        with self.assertRaises(SQLRejectedError):
            validate_sql(sql, self.context)

    def test_rejects_other_or_missing_schema(self) -> None:
        candidates = (
            "SELECT * FROM public.fct_sales_order_line",
            "SELECT * FROM pg_catalog.pg_tables",
            "SELECT * FROM information_schema.tables",
            "SELECT * FROM fct_sales_order_line",
        )

        for sql in candidates:
            with self.subTest(sql=sql):
                with self.assertRaises(SQLRejectedError):
                    validate_sql(sql, self.context)

    def test_rejects_unknown_table_or_column(self) -> None:
        candidates = (
            "SELECT * FROM mart_sales.unknown_table",
            "SELECT unknown_column FROM mart_sales.fct_sales_order_line",
            "SELECT f.unknown_column FROM mart_sales.fct_sales_order_line AS f",
        )

        for sql in candidates:
            with self.subTest(sql=sql):
                with self.assertRaises(SQLRejectedError):
                    validate_sql(sql, self.context)

    def test_rejects_ambiguous_unqualified_column(self) -> None:
        sql = """
SELECT customer_key
FROM mart_sales.fct_sales_order_line AS f
JOIN mart_sales.dim_customer AS c ON c.customer_key = f.customer_key
"""

        with self.assertRaises(SQLRejectedError):
            validate_sql(sql, self.context)

    def test_rejects_select_without_physical_table(self) -> None:
        with self.assertRaises(SQLRejectedError):
            validate_sql("SELECT 1", self.context)

    def test_rejects_locking_and_select_into(self) -> None:
        candidates = (
            "SELECT * FROM mart_sales.fct_sales_order_line FOR UPDATE",
            "SELECT * INTO temporary copied_orders "
            "FROM mart_sales.fct_sales_order_line",
        )

        for sql in candidates:
            with self.subTest(sql=sql):
                with self.assertRaises(SQLRejectedError):
                    validate_sql(sql, self.context)

    def test_rejects_dangerous_postgresql_functions(self) -> None:
        candidates = (
            "SELECT pg_sleep(1) FROM mart_sales.fct_sales_order_line",
            "SELECT set_config('search_path', 'public', false) "
            "FROM mart_sales.fct_sales_order_line",
            "SELECT pg_read_file('/tmp/x') "
            "FROM mart_sales.fct_sales_order_line",
            "SELECT public.side_effect(order_id) "
            "FROM mart_sales.fct_sales_order_line",
        )

        for sql in candidates:
            with self.subTest(sql=sql):
                with self.assertRaises(SQLRejectedError):
                    validate_sql(sql, self.context)


if __name__ == "__main__":
    unittest.main()
