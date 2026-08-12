"""Sales Mart V1 Demo Data 自动化测试。

测试分为两层：
1. 无数据库的 Deterministic Test（确定性测试）：证明固定 seed 产生相同数据、规模和 SCD2 版本；
2. PostgreSQL Integration Test（数据库集成测试）：证明 reset + reseed 可重复、业务约束与 public 基线不受影响。

测试会留下最后一次成功生成的 Demo Data（演示数据），便于后续人工/指标验证；不会产生额外测试表或修改 public 数据。
"""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
from typing import Any

import psycopg

from scripts.seed_sales_mart import (
    DATABASE_NAME,
    END_DATE,
    START_DATE,
    connection_config,
    fetch_report,
    generate_data,
    load_data,
    parse_env,
    reset_mart_sales,
    validate_report,
)


ROOT = Path(__file__).resolve().parents[1]


class SalesMartSeedTest(unittest.TestCase):
    conn: psycopg.Connection[Any]

    @classmethod
    def setUpClass(cls) -> None:
        env = parse_env(ROOT / ".env")
        cls.conn = psycopg.connect(**connection_config(env))
        cls.conn.autocommit = False
        with cls.conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            if cur.fetchone()[0] != DATABASE_NAME:
                raise RuntimeError(f"拒绝在非目标数据库执行 Demo Data 测试：{DATABASE_NAME}")
            cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")
            cls.public_table_count = int(cur.fetchone()[0])
            if cls.public_table_count != 5:
                raise RuntimeError(f"public 旧基线表数量异常：{cls.public_table_count}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.conn.rollback()
        cls.conn.close()

    @staticmethod
    def _fingerprint(data: Any) -> str:
        payload = repr(
            (
                data.dates,
                data.currencies,
                data.regions,
                data.customers,
                data.products,
                data.rates,
                data.sales_lines,
            )
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def test_fixed_seed_is_deterministic(self) -> None:
        first = generate_data(seed=42)
        second = generate_data(seed=42)
        self.assertEqual(self._fingerprint(first), self._fingerprint(second))
        self.assertNotEqual(self._fingerprint(first), self._fingerprint(generate_data(seed=43)))

    def test_default_scale_and_scd2_versions_are_in_range(self) -> None:
        data = generate_data(seed=42)
        self.assertEqual(len(data.dates), 731)
        self.assertEqual(len(data.currencies), 4)
        self.assertEqual(len(data.regions), 6)
        self.assertEqual(len(data.rates), 731 * 4)
        self.assertEqual(len(data.customers), 224)
        self.assertEqual(len(data.products), 90)
        self.assertTrue(8_000 <= len(data.sales_lines) <= 12_000)
        self.assertEqual(sum(len(versions) > 1 for versions in data.customer_versions.values()), 24)
        self.assertEqual(sum(len(versions) > 1 for versions in data.product_versions.values()), 10)
        self.assertTrue(
            all(
                versions[0].attributes != versions[1].attributes
                for versions in data.customer_versions.values()
                if len(versions) > 1
            )
        )
        self.assertTrue(
            all(
                versions[0].attributes != versions[1].attributes
                for versions in data.product_versions.values()
                if len(versions) > 1
            )
        )
        self.assertTrue(
            all(
                versions[0].attributes[0] == versions[1].attributes[0]
                and versions[0].attributes[3] == versions[1].attributes[3]
                for versions in data.customer_versions.values()
                if len(versions) > 1
            )
        )
        self.assertTrue(
            all(
                versions[0].attributes[0] == versions[1].attributes[0]
                for versions in data.product_versions.values()
                if len(versions) > 1
            )
        )
        valid_customer_keys = {
            10_000 + customer_id * 10 + (1 if version.is_current else 0)
            for customer_id, versions in data.customer_versions.items()
            for version in versions
        }
        self.assertTrue(
            all(
                row[5] in valid_customer_keys
                for row in data.sales_lines
            )
        )

    def test_generated_sales_lines_have_valid_status_and_completed_facts(self) -> None:
        data = generate_data(seed=42)
        statuses = {row[12] for row in data.sales_lines}
        self.assertEqual(statuses, {"pending", "confirmed", "completed", "cancelled"})
        for row in data.sales_lines:
            status = row[12]
            self.assertEqual(row[3], row[0])
            if status == "completed":
                self.assertIsNotNone(row[11])
                self.assertIsNotNone(row[18])
                self.assertIsNotNone(row[19])
                self.assertIsNotNone(row[20])
                self.assertIsNotNone(row[21])
            else:
                self.assertIsNone(row[11])
                self.assertIsNone(row[18])
                self.assertIsNone(row[19])
                self.assertIsNone(row[20])
                self.assertIsNone(row[21])

    def test_reset_reseed_and_database_validation(self) -> None:
        data = generate_data(seed=42)
        with self.conn.cursor() as cur:
            reset_mart_sales(cur)
            load_data(self.conn, data, reset=False)
            first_report = fetch_report(self.conn)
            first_failures = validate_report(self.conn, data, first_report)
            self.assertEqual(first_failures, [])
            first_counts = dict(first_report.row_counts)
            first_metrics = dict(first_report.metrics)
            self.conn.commit()

            reset_mart_sales(cur)
            load_data(self.conn, data, reset=False)
            second_report = fetch_report(self.conn)
            second_failures = validate_report(self.conn, data, second_report)
            self.assertEqual(second_failures, [])
            self.assertEqual(second_report.row_counts, first_counts)
            self.assertEqual(second_report.metrics, first_metrics)
            cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")
            self.assertEqual(cur.fetchone()[0], self.public_table_count)
            self.conn.commit()


if __name__ == "__main__":
    unittest.main(verbosity=2)
