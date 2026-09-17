"""SQL Guard（SQL 安全校验）测试。"""

import json
from pathlib import Path
import unittest
from unittest.mock import patch

from src.online_query.contracts import (
    JoinConstraint,
    MetricConstraint,
    QueryContext,
    RequestShape,
)
from src.online_query.context import load_query_context
from src.online_query.sql_guard import SQLRejectedError, validate_sql
import src.online_query.sql_guard as sql_guard


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
                "mart_sales.dim_customer": frozenset({"customer_key", "customer_name"}),
            },
            join_constraints=(
                JoinConstraint(
                    source_table="mart_sales.fct_sales_order_line",
                    source_columns=("customer_key",),
                    target_table="mart_sales.dim_customer",
                    target_columns=("customer_key",),
                    uniqueness_basis="primary_key:pk_dim_customer",
                    direction="forward",
                ),
            ),
        )
        cls.multi_context = _multi_metric_context()

    def test_valid_select_passes_without_rewriting(self) -> None:
        sql = (
            "SELECT f.order_id, SUM(f.net_sales_amount_cny) AS revenue "
            "FROM mart_sales.fct_sales_order_line AS f "
            "WHERE f.order_status = 'completed' "
            "GROUP BY f.order_id ORDER BY revenue DESC;"
        )

        validated = validate_sql(sql, self.context)

        self.assertEqual(validated.sql, sql)

    def test_standalone_validate_sql_parses_once(self) -> None:
        sql = "SELECT order_id FROM mart_sales.fct_sales_order_line"

        with patch(
            "src.online_query.sql_guard._parse_single_select",
            wraps=sql_guard._parse_single_select,
        ) as parse:
            validated = validate_sql(sql, self.context)

        self.assertEqual(validated.sql, sql)
        self.assertEqual(parse.call_count, 1)

    def test_valid_direct_left_join_uses_graph_constraint(self) -> None:
        sql = (
            "SELECT c.customer_name, SUM(f.net_sales_amount_cny) AS revenue "
            "FROM mart_sales.fct_sales_order_line AS f "
            "LEFT JOIN mart_sales.dim_customer AS c "
            "ON f.customer_key = c.customer_key "
            "GROUP BY c.customer_name"
        )

        validated = validate_sql(sql, self.context)

        self.assertEqual(validated.sql, sql)

    def test_direct_join_rejects_wrong_direction_or_unregistered_key(self) -> None:
        candidates = (
            (
                "SELECT c.customer_name FROM mart_sales.fct_sales_order_line AS f "
                "RIGHT JOIN mart_sales.dim_customer AS c "
                "ON f.customer_key = c.customer_key"
            ),
            (
                "SELECT c.customer_name FROM mart_sales.fct_sales_order_line AS f "
                "LEFT JOIN mart_sales.dim_customer AS c "
                "ON f.order_id = c.customer_key"
            ),
        )

        for sql in candidates:
            with self.subTest(sql=sql):
                with self.assertRaises(SQLRejectedError):
                    validate_sql(sql, self.context)

    def test_valid_multi_metric_select_passes_without_rewriting(self) -> None:
        sql = _valid_multi_metric_sql()

        validated = validate_sql(sql, self.multi_context)

        self.assertEqual(validated.sql, sql)

    def test_multi_metric_allows_parentheses_and_alias_variations(self) -> None:
        sql = _valid_multi_metric_sql()
        sql = sql.replace(
            "COUNT(DISTINCT f.order_id) AS completed_order_count",
            "((COUNT(DISTINCT f.order_id))) AS completed_order_count",
        )
        sql = sql.replace(
            "WHERE f.order_status = 'completed'",
            "WHERE (f.order_status = 'completed')",
        )

        validated = validate_sql(sql, self.multi_context)

        self.assertEqual(validated.sql, sql)

    def test_multi_metric_rejects_incomplete_extra_or_reordered_outputs(self) -> None:
        candidates = (
            _valid_multi_metric_sql().replace(
                "       SUM(f.net_sales_amount_cny) AS net_sales_cny,\n",
                "",
            ),
            _valid_multi_metric_sql().replace(
                "       SUM(f.net_sales_amount_cny) AS net_sales_cny,",
                "       SUM(f.sales_cost_amount_cny) AS sales_cost_cny,",
            ),
            _valid_multi_metric_sql().replace(
                "       SUM(f.net_sales_amount_cny) AS net_sales_cny,\n"
                "       SUM(f.net_sales_amount_cny - f.sales_cost_amount_cny)\n"
                "           / NULLIF(SUM(f.net_sales_amount_cny), 0) "
                "AS gross_margin",
                "       SUM(f.net_sales_amount_cny - f.sales_cost_amount_cny)\n"
                "           / NULLIF(SUM(f.net_sales_amount_cny), 0) "
                "AS gross_margin,\n"
                "       SUM(f.net_sales_amount_cny) AS net_sales_cny",
            ),
        )

        for sql in candidates:
            with self.subTest(sql=sql):
                with self.assertRaises(SQLRejectedError):
                    validate_sql(sql, self.multi_context)

    def test_multi_metric_rejects_formula_fixed_filter_or_and_wrong_join(self) -> None:
        candidates = (
            _valid_multi_metric_sql().replace(
                "SUM(f.net_sales_amount_cny - f.sales_cost_amount_cny)",
                "SUM(f.net_sales_amount_cny + f.sales_cost_amount_cny)",
            ),
            _valid_multi_metric_sql().replace(
                "WHERE f.order_status = 'completed'\n",
                "",
            ),
            _valid_multi_metric_sql().replace(
                "WHERE f.order_status = 'completed'",
                "WHERE f.order_status = 'completed' OR f.order_status = 'pending'",
            ),
            _valid_multi_metric_sql().replace(
                "ON f.customer_key = c.customer_key",
                "ON f.customer_key = c.customer_name",
            ),
        )

        for sql in candidates:
            with self.subTest(sql=sql):
                with self.assertRaises(SQLRejectedError):
                    validate_sql(sql, self.multi_context)

    def test_multi_metric_rejects_unsupported_shapes_and_extra_aggregation(
        self,
    ) -> None:
        candidates = (
            """
WITH base AS (
    SELECT *
    FROM mart_sales.fct_sales_order_line
)
SELECT c.customer_type,
       COUNT(DISTINCT f.order_id),
       SUM(f.net_sales_amount_cny),
       SUM(f.net_sales_amount_cny - f.sales_cost_amount_cny)
           / NULLIF(SUM(f.net_sales_amount_cny), 0)
FROM base AS f
JOIN mart_sales.dim_customer AS c
  ON f.customer_key = c.customer_key
WHERE f.order_status = 'completed'
GROUP BY c.customer_type
""".strip(),
            _valid_multi_metric_sql().replace(
                "GROUP BY c.customer_type",
                "GROUP BY c.customer_type HAVING SUM(f.net_sales_amount_cny) > 0",
            ),
            _valid_multi_metric_sql().replace(
                "ORDER BY gross_margin DESC",
                "ORDER BY SUM(f.sales_cost_amount_cny) DESC",
            ),
        )

        for sql in candidates:
            with self.subTest(sql=sql):
                with self.assertRaises(SQLRejectedError):
                    validate_sql(sql, self.multi_context)

    def test_cte_join_and_output_alias_is_rejected_by_v1_shape(self) -> None:
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

        with self.assertRaises(SQLRejectedError):
            validate_sql(sql, self.context)

    def test_cte_without_join_is_rejected_by_v1_shape(self) -> None:
        sql = """
WITH sales AS (
    SELECT order_id
    FROM mart_sales.fct_sales_order_line
)
SELECT order_id
FROM sales
""".strip()

        with self.assertRaises(SQLRejectedError):
            validate_sql(sql, self.context)

    def test_all_metric_sql_templates_pass(self) -> None:
        root = Path(__file__).resolve().parents[2]
        metrics = json.loads(
            (root / "src" / "semantic" / "metrics.json").read_text(encoding="utf-8")
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
            "SELECT pg_read_file('/tmp/x') FROM mart_sales.fct_sales_order_line",
            "SELECT public.side_effect(order_id) FROM mart_sales.fct_sales_order_line",
        )

        for sql in candidates:
            with self.subTest(sql=sql):
                with self.assertRaises(SQLRejectedError):
                    validate_sql(sql, self.context)


def _multi_metric_context() -> QueryContext:
    fact_table = "mart_sales.fct_sales_order_line"
    customer_table = "mart_sales.dim_customer"
    constraints = (
        MetricConstraint(
            ordinal=1,
            requested_text="已完成订单数",
            document_id="metric:completed_orders",
            metric_name="已完成订单数",
            formula="COUNT(DISTINCT f.order_id)",
            data_source=fact_table,
            time_field="fct_sales_order_line.completion_date_key -> dim_date.full_date",
            filters=("f.order_status = 'completed'",),
            depends_on=(),
        ),
        MetricConstraint(
            ordinal=2,
            requested_text="人民币销售额",
            document_id="metric:net_sales",
            metric_name="人民币净销售额",
            formula="SUM(f.net_sales_amount_cny)",
            data_source=fact_table,
            time_field="fct_sales_order_line.completion_date_key -> dim_date.full_date",
            filters=("f.order_status = 'completed'",),
            depends_on=(),
        ),
        MetricConstraint(
            ordinal=3,
            requested_text="毛利率",
            document_id="metric:gross_margin",
            metric_name="毛利率",
            formula=(
                "SUM(f.net_sales_amount_cny - f.sales_cost_amount_cny) "
                "/ NULLIF(SUM(f.net_sales_amount_cny), 0)"
            ),
            data_source=fact_table,
            time_field="fct_sales_order_line.completion_date_key -> dim_date.full_date",
            filters=("f.order_status = 'completed'",),
            depends_on=("人民币毛利", "人民币净销售额"),
        ),
    )
    return QueryContext(
        prompt_context="{}",
        allowed_tables=frozenset({fact_table, customer_table}),
        allowed_columns={
            fact_table: frozenset(
                {
                    "customer_key",
                    "order_id",
                    "net_sales_amount_cny",
                    "sales_cost_amount_cny",
                    "order_status",
                }
            ),
            customer_table: frozenset(
                {"customer_key", "customer_type", "customer_name"}
            ),
        },
        request_shape=RequestShape.EXPLICIT_MULTI,
        metric_constraints=constraints,
        join_constraints=(
            JoinConstraint(
                source_table=fact_table,
                source_columns=("customer_key",),
                target_table=customer_table,
                target_columns=("customer_key",),
                uniqueness_basis="primary_key:dim_customer",
                direction="forward",
            ),
        ),
    )


def _valid_multi_metric_sql() -> str:
    return """
SELECT c.customer_type,
       COUNT(DISTINCT f.order_id) AS completed_order_count,
       SUM(f.net_sales_amount_cny) AS net_sales_cny,
       SUM(f.net_sales_amount_cny - f.sales_cost_amount_cny)
           / NULLIF(SUM(f.net_sales_amount_cny), 0) AS gross_margin
FROM mart_sales.fct_sales_order_line AS f
LEFT JOIN mart_sales.dim_customer AS c
  ON f.customer_key = c.customer_key
WHERE f.order_status = 'completed'
GROUP BY c.customer_type
ORDER BY gross_margin DESC
""".strip()


if __name__ == "__main__":
    unittest.main()
