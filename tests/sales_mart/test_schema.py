"""Sales Mart V1 Schema Test（销售数据集市 V1 结构测试）。

职责：
1. 在配置的 PostgreSQL 数据库中幂等执行 Sales Mart DDL；
2. 验证 7 张目标表、主键、外键、SCD2 和事实完整性约束；
3. 将测试维度/事实写入同一事务，并在每个测试结束时回滚，不留下测试业务行。

边界：
- 只会持久化本任务要求的 mart_sales 结构；
- 不删除或重建 public Schema（旧教程基线）；
- 不读取或输出 .env 中的密码、Token（令牌）或其他 Secret（敏感信息）。
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import psycopg


ROOT = Path(__file__).resolve().parents[2]
DDL_PATH = ROOT / "database" / "sales_mart" / "001_create_schema.sql"
SCHEMA = "mart_sales"
TEST_SOURCE_SYSTEM = "sales_mart_schema_test"
TEST_TIMESTAMP = datetime(2099, 1, 1, tzinfo=timezone.utc)


def load_env(path: Path) -> dict[str, str]:
    """读取本地配置；只返回内存中的键值，不打印敏感值。"""

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def connection_config(env: dict[str, str]) -> dict[str, Any]:
    required = ["POSTGRES_MIGRATOR_USER", "POSTGRES_MIGRATOR_PASSWORD"]
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise ValueError(f".env 缺少必要配置：{', '.join(missing)}")
    return {
        "host": env.get("POSTGRES_HOST", "127.0.0.1"),
        "port": int(env.get("POSTGRES_PORT", "5432")),
        "dbname": env.get("POSTGRES_DB", "chatbi_mvp"),
        "user": env["POSTGRES_MIGRATOR_USER"],
        "password": env["POSTGRES_MIGRATOR_PASSWORD"],
        "connect_timeout": 10,
    }


class SalesMartSchemaTest(unittest.TestCase):
    conn: psycopg.Connection[Any]
    database_name: str

    @classmethod
    def setUpClass(cls) -> None:
        env = load_env(ROOT / ".env")
        cls.conn = psycopg.connect(**connection_config(env))
        cls.conn.autocommit = False
        with cls.conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            cls.database_name = str(cur.fetchone()[0])
        ddl = DDL_PATH.read_text(encoding="utf-8")
        with cls.conn.cursor() as cur:
            cur.execute(ddl)
        cls.conn.commit()
        # 第二次执行用于证明当前无漂移时初始化脚本可重复执行。
        with cls.conn.cursor() as cur:
            cur.execute(ddl)
        cls.conn.commit()
        print(f"Sales Mart DDL applied: database={cls.database_name}, schema={SCHEMA}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.conn.rollback()
        cls.conn.close()

    def setUp(self) -> None:
        self.conn.rollback()
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mart_sales.dim_date
                    (date_key, full_date, year, quarter, month, day)
                VALUES
                    (20990101, DATE '2099-01-01', 2099, 1, 1, 1),
                    (20990102, DATE '2099-01-02', 2099, 1, 1, 2)
                """
            )
            cur.execute(
                """
                INSERT INTO mart_sales.dim_customer
                    (customer_key, customer_id, customer_name, customer_type,
                     industry, country, customer_region, valid_from,
                     is_current, source_system, source_updated_at)
                VALUES
                    (-1001, -2001, '测试客户', 'enterprise', 'energy', 'CN', '华东',
                     %s, TRUE, %s, %s)
                """,
                (TEST_TIMESTAMP, TEST_SOURCE_SYSTEM, TEST_TIMESTAMP),
            )
            cur.execute(
                """
                INSERT INTO mart_sales.dim_product
                    (product_key, product_id, product_name, product_line,
                     product_category, technology_route, valid_from,
                     is_current, source_system, source_updated_at)
                VALUES
                    (-1101, -2101, '测试产品', '测试产品线', '测试类别', '测试路线',
                     %s, TRUE, %s, %s)
                """,
                (TEST_TIMESTAMP, TEST_SOURCE_SYSTEM, TEST_TIMESTAMP),
            )
            cur.execute(
                """
                INSERT INTO mart_sales.dim_sales_region
                    (sales_region_key, sales_region_code, sales_region_name)
                VALUES (-1201, 'TEST-EAST', '测试销售区域')
                """
            )
            cur.execute(
                """
                INSERT INTO mart_sales.dim_currency
                    (currency_key, currency_code, currency_name, is_analysis_currency)
                VALUES (-1301, 'TST', '测试币种', FALSE)
                """
            )

    def tearDown(self) -> None:
        self.conn.rollback()

    def _line_values(self, **overrides: Any) -> dict[str, Any]:
        values: dict[str, Any] = {
            "sales_order_line_key": -1401,
            "order_id": -3001,
            "order_no": "TEST-SO-3001",
            "order_line_id": -4001,
            "order_line_no": 1,
            "customer_key": -1001,
            "product_key": -1101,
            "sales_region_key": -1201,
            "transaction_currency_key": -1301,
            "order_date_key": 20990101,
            "confirmation_date_key": 20990101,
            "completion_date_key": 20990102,
            "order_status": "completed",
            "quantity": 2,
            "unit_price_transaction": 100,
            "discount_amount_transaction": 5,
            "gross_sales_amount_transaction": 200,
            "net_sales_amount_transaction": 195,
            "fx_rate_to_cny": 1,
            "net_sales_amount_cny": 195,
            "frozen_unit_cost_cny": 60,
            "sales_cost_amount_cny": 120,
            "source_system": TEST_SOURCE_SYSTEM,
            "source_updated_at": TEST_TIMESTAMP,
        }
        values.update(overrides)
        return values

    def _insert_line(self, cur: Any, **overrides: Any) -> None:
        values = self._line_values(**overrides)
        cur.execute(
            """
            INSERT INTO mart_sales.fct_sales_order_line (
                sales_order_line_key, order_id, order_no, order_line_id, order_line_no,
                customer_key, product_key, sales_region_key, transaction_currency_key,
                order_date_key, confirmation_date_key, completion_date_key, order_status,
                quantity, unit_price_transaction, discount_amount_transaction,
                gross_sales_amount_transaction, net_sales_amount_transaction,
                fx_rate_to_cny, net_sales_amount_cny, frozen_unit_cost_cny,
                sales_cost_amount_cny, source_system, source_updated_at
            )
            VALUES (
                %(sales_order_line_key)s, %(order_id)s, %(order_no)s,
                %(order_line_id)s, %(order_line_no)s, %(customer_key)s,
                %(product_key)s, %(sales_region_key)s, %(transaction_currency_key)s,
                %(order_date_key)s, %(confirmation_date_key)s, %(completion_date_key)s,
                %(order_status)s, %(quantity)s, %(unit_price_transaction)s,
                %(discount_amount_transaction)s, %(gross_sales_amount_transaction)s,
                %(net_sales_amount_transaction)s, %(fx_rate_to_cny)s,
                %(net_sales_amount_cny)s, %(frozen_unit_cost_cny)s,
                %(sales_cost_amount_cny)s, %(source_system)s, %(source_updated_at)s
            )
            """,
            values,
        )

    def _expect_integrity_error(self, operation: Callable[[Any], None]) -> None:
        savepoint = "sales_mart_expected_failure"
        with self.conn.cursor() as cur:
            cur.execute(f"SAVEPOINT {savepoint}")
            try:
                operation(cur)
            except psycopg.IntegrityError:
                cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                cur.execute(f"RELEASE SAVEPOINT {savepoint}")
            else:
                cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                cur.execute(f"RELEASE SAVEPOINT {savepoint}")
                self.fail("预期的数据库完整性约束没有拒绝非法写入")

    def test_schema_contains_exactly_seven_target_tables(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """,
                (SCHEMA,),
            )
            actual = [row[0] for row in cur.fetchall()]
        self.assertEqual(
            actual,
            [
                "dim_currency",
                "dim_customer",
                "dim_date",
                "dim_product",
                "dim_sales_region",
                "fct_exchange_rate_daily",
                "fct_sales_order_line",
            ],
        )

    def test_primary_foreign_and_unique_constraints_exist(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.contype, pg_get_constraintdef(c.oid)
                FROM pg_constraint AS c
                JOIN pg_class AS r ON r.oid = c.conrelid
                JOIN pg_namespace AS n ON n.oid = r.relnamespace
                WHERE n.nspname = %s AND c.contype IN ('p', 'f', 'u')
                """,
                (SCHEMA,),
            )
            constraints = cur.fetchall()
        self.assertEqual(sum(row[0] == "p" for row in constraints), 7)
        self.assertEqual(sum(row[0] == "f" for row in constraints), 9)
        definitions = [row[1] for row in constraints]
        self.assertTrue(any("PRIMARY KEY (rate_date_key, currency_key)" in d for d in definitions))
        self.assertTrue(any("FOREIGN KEY (completion_date_key)" in d for d in definitions))
        self.assertTrue(any("FOREIGN KEY (customer_key)" in d for d in definitions))
        self.assertTrue(any("UNIQUE (order_line_id)" in d for d in definitions))
        self.assertTrue(any("UNIQUE (order_id, order_line_no)" in d for d in definitions))

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = %s
                """,
                (SCHEMA,),
            )
            indexes = {row[0] for row in cur.fetchall()}
        self.assertIn("ux_dim_customer_current", indexes)
        self.assertIn("ux_dim_product_current", indexes)
        self.assertIn("idx_fct_sales_order_line_completion_status", indexes)

    def test_scd2_historical_version_is_allowed(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mart_sales.dim_customer
                    (customer_key, customer_id, customer_name, customer_type,
                     industry, country, customer_region, valid_from, valid_to,
                     is_current, source_system, source_updated_at)
                VALUES
                    (-1002, -2001, '测试客户旧版', 'enterprise', 'energy', 'CN', '华北',
                     TIMESTAMPTZ '2098-01-01 00:00:00+00',
                     TIMESTAMPTZ '2098-12-31 23:59:59+00', FALSE, %s, %s)
                """,
                (TEST_SOURCE_SYSTEM, TEST_TIMESTAMP),
            )
            cur.execute(
                """
                INSERT INTO mart_sales.dim_product
                    (product_key, product_id, product_name, product_line,
                     product_category, technology_route, valid_from, valid_to,
                     is_current, source_system, source_updated_at)
                VALUES
                    (-1102, -2101, '测试产品旧版', '旧产品线', '旧类别', '旧路线',
                     TIMESTAMPTZ '2098-01-01 00:00:00+00',
                     TIMESTAMPTZ '2098-12-31 23:59:59+00', FALSE, %s, %s)
                """,
                (TEST_SOURCE_SYSTEM, TEST_TIMESTAMP),
            )
            cur.execute(
                """
                SELECT COUNT(*)
                FROM mart_sales.dim_customer
                WHERE customer_id = -2001
                """
            )
            customer_count = cur.fetchone()[0]
            cur.execute(
                """
                SELECT COUNT(*)
                FROM mart_sales.dim_product
                WHERE product_id = -2101
                """
            )
            product_count = cur.fetchone()[0]
        self.assertEqual(customer_count, 2)
        self.assertEqual(product_count, 2)

    def test_scd2_customer_current_version_is_unique(self) -> None:
        self._expect_integrity_error(
            lambda cur: cur.execute(
                """
                INSERT INTO mart_sales.dim_customer
                    (customer_key, customer_id, customer_name, customer_type,
                     industry, country, customer_region, valid_from,
                     is_current, source_system, source_updated_at)
                VALUES
                    (-1003, -2001, '测试客户重复当前版', 'enterprise', 'energy', 'CN', '华南',
                     TIMESTAMPTZ '2100-01-01 00:00:00+00', TRUE, %s, %s)
                """,
                (TEST_SOURCE_SYSTEM, TEST_TIMESTAMP),
            )
        )

    def test_scd2_product_current_version_is_unique(self) -> None:
        self._expect_integrity_error(
            lambda cur: cur.execute(
                """
                INSERT INTO mart_sales.dim_product
                    (product_key, product_id, product_name, product_line,
                     product_category, technology_route, valid_from,
                     is_current, source_system, source_updated_at)
                VALUES
                    (-1103, -2101, '测试产品重复当前版', '测试产品线', '测试类别', '测试路线',
                     TIMESTAMPTZ '2100-01-01 00:00:00+00', TRUE, %s, %s)
                """,
                (TEST_SOURCE_SYSTEM, TEST_TIMESTAMP),
            )
        )

    def test_duplicate_order_line_id_is_rejected(self) -> None:
        with self.conn.cursor() as cur:
            self._insert_line(cur)
            self._expect_integrity_error(
                lambda inner: self._insert_line(
                    inner,
                    sales_order_line_key=-1402,
                    order_id=-3002,
                    order_no="TEST-SO-3002",
                    order_line_id=-4001,
                    order_line_no=1,
                )
            )

    def test_duplicate_order_and_line_number_is_rejected(self) -> None:
        with self.conn.cursor() as cur:
            self._insert_line(cur)
            self._expect_integrity_error(
                lambda inner: self._insert_line(
                    inner,
                    sales_order_line_key=-1403,
                    order_no="TEST-SO-3001-RETRY",
                    order_line_id=-4003,
                    order_line_no=1,
                )
            )

    def test_completed_line_missing_completion_date_is_rejected(self) -> None:
        self._expect_integrity_error(
            lambda cur: self._insert_line(cur, completion_date_key=None)
        )

    def test_completed_line_missing_fx_rate_is_rejected(self) -> None:
        self._expect_integrity_error(
            lambda cur: self._insert_line(cur, fx_rate_to_cny=None)
        )

    def test_completed_line_missing_cny_revenue_is_rejected(self) -> None:
        self._expect_integrity_error(
            lambda cur: self._insert_line(cur, net_sales_amount_cny=None)
        )

    def test_completed_line_missing_frozen_sales_cost_is_rejected(self) -> None:
        self._expect_integrity_error(
            lambda cur: self._insert_line(
                cur, frozen_unit_cost_cny=None, sales_cost_amount_cny=None
            )
        )

    def test_invalid_order_status_is_rejected(self) -> None:
        self._expect_integrity_error(
            lambda cur: self._insert_line(cur, order_status="returned")
        )

    def test_non_positive_exchange_rate_is_rejected(self) -> None:
        self._expect_integrity_error(
            lambda cur: cur.execute(
                """
                INSERT INTO mart_sales.fct_exchange_rate_daily
                    (rate_date_key, currency_key, rate_to_cny,
                     source_system, source_updated_at)
                VALUES (20990101, -1301, 0, %s, %s)
                """,
                (TEST_SOURCE_SYSTEM, TEST_TIMESTAMP),
            )
        )

    def test_dimension_and_date_foreign_keys_reject_orphans(self) -> None:
        self._expect_integrity_error(
            lambda cur: self._insert_line(cur, customer_key=-999999)
        )
        self._expect_integrity_error(
            lambda cur: cur.execute(
                """
                INSERT INTO mart_sales.fct_exchange_rate_daily
                    (rate_date_key, currency_key, rate_to_cny,
                     source_system, source_updated_at)
                VALUES (20991231, -1301, 1, %s, %s)
                """,
                (TEST_SOURCE_SYSTEM, TEST_TIMESTAMP),
            )
        )

    def test_complete_sales_order_line_and_exchange_rate_can_be_inserted(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mart_sales.fct_exchange_rate_daily
                    (rate_date_key, currency_key, rate_to_cny,
                     source_system, source_updated_at)
                VALUES (20990102, -1301, 1, %s, %s)
                """,
                (TEST_SOURCE_SYSTEM, TEST_TIMESTAMP),
            )
            self._insert_line(cur)
            cur.execute(
                """
                SELECT order_id, order_line_id, order_status,
                       net_sales_amount_cny, sales_cost_amount_cny
                FROM mart_sales.fct_sales_order_line
                WHERE sales_order_line_key = -1401
                """
            )
            row = cur.fetchone()
        self.assertEqual(row, (-3001, -4001, "completed", 195, 120))


if __name__ == "__main__":
    unittest.main(verbosity=2)
