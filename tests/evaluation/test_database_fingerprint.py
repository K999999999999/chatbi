"""Sales Mart data fingerprint tests, including the isolated development DB."""

import os
import unittest
from contextlib import AbstractContextManager
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import psycopg

from src.evaluation.database_fingerprint import (
    SalesMartFingerprintError,
    collect_sales_mart_fingerprint,
)

_TABLES = {
    "dim_date": (
        ("date_key", "full_date", "year", "quarter", "month", "day"),
        ((20250101, date(2025, 1, 1), 2025, 1, 1, 1),),
    ),
    "dim_customer": (
        ("customer_key", "customer_id", "customer_name"),
        ((1001, 1001, "Test Customer"),),
    ),
    "dim_product": (
        ("product_key", "product_id", "product_name"),
        ((2001, 2001, "Test Product"),),
    ),
    "dim_sales_region": (("sales_region_key", "sales_region_name"), ((3001, "East"),)),
    "dim_currency": (("currency_key", "currency_code"), ((4001, "CNY"),)),
    "fct_exchange_rate_daily": (
        ("rate_date_key", "currency_key", "rate_to_cny"),
        ((20250101, 4001, 1),),
    ),
    "fct_sales_order_line": (
        ("sales_order_line_key", "net_sales_amount_cny"),
        ((2000011, 1200),),
    ),
}


class _FakeConnection(AbstractContextManager):
    def __init__(
        self, tables, *, user="chatbi_app", database="chatbi_mvp", seed="seed-v1"
    ):
        self._cursor = _FakeCursor(tables, user=user, database=database, seed=seed)

    def cursor(self):
        return self._cursor

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class _FakeCursor(AbstractContextManager):
    def __init__(self, tables, *, user, database, seed):
        self._tables = tables
        self._user = user
        self._database = database
        self._seed = seed
        self._row = None
        self.description = None

    def execute(self, query):
        if query.startswith("SET TRANSACTION"):
            return
        if query.startswith("SELECT current_user"):
            self._row = (self._user, self._database)
        elif "dev_seed_metadata" in query:
            self._row = (self._seed,) if self._seed else None
        else:
            table_name = query.split('mart_sales."', 1)[1].split('"', 1)[0]
            columns, rows = self._tables[table_name]
            self.description = tuple(SimpleNamespace(name=name) for name in columns)
            self._row = rows

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._row

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class SalesMartFingerprintTest(unittest.TestCase):
    def test_hash_and_summary_repeat_for_the_same_database_snapshot(self) -> None:
        connect = _connector(_TABLES)
        first = collect_sales_mart_fingerprint(_environment(), connect=connect)
        second = collect_sales_mart_fingerprint(_environment(), connect=connect)

        self.assertEqual(first, second)
        self.assertEqual(first.seed_version, "seed-v1")
        self.assertEqual(first.data_summary["total_rows"], len(_TABLES))
        self.assertEqual(
            first.data_summary["date_range"],
            {"start": "2025-01-01", "end": "2025-01-01"},
        )
        self.assertEqual(len(first.data_hash), 64)

    def test_actual_row_change_changes_hash_without_exposing_rows(self) -> None:
        changed_tables = dict(_TABLES)
        changed_tables["fct_sales_order_line"] = (
            _TABLES["fct_sales_order_line"][0],
            ((2000011, 1201),),
        )

        before = collect_sales_mart_fingerprint(
            _environment(), connect=_connector(_TABLES)
        )
        after = collect_sales_mart_fingerprint(
            _environment(),
            connect=_connector(changed_tables),
        )

        self.assertNotEqual(before.data_hash, after.data_hash)
        serialized_summary = str(after.data_summary)
        self.assertNotIn("1201", serialized_summary)
        self.assertNotIn("Test Customer", serialized_summary)

    def test_fingerprint_requires_chatbi_mvp_and_read_only_account(self) -> None:
        connect = Mock()
        with self.assertRaisesRegex(SalesMartFingerprintError, "chatbi_mvp"):
            collect_sales_mart_fingerprint(
                {**_environment(), "POSTGRES_DB": "chatbi_evaluation"},
                connect=connect,
            )
        with self.assertRaisesRegex(SalesMartFingerprintError, "chatbi_app"):
            collect_sales_mart_fingerprint(
                {**_environment(), "POSTGRES_APP_USER": "chatbi_migrator"},
                connect=connect,
            )
        connect.assert_not_called()

    def test_missing_seed_version_fails_closed(self) -> None:
        with self.assertRaisesRegex(SalesMartFingerprintError, "Seed 版本"):
            collect_sales_mart_fingerprint(
                _environment(),
                connect=_connector(_TABLES, seed=None),
            )


@unittest.skipUnless(
    os.environ.get("RUN_DEVELOPMENT_DATABASE_TESTS") == "1",
    "run scripts/run_database_tests.py --profile development",
)
class SalesMartFingerprintPostgresTest(unittest.TestCase):
    def test_hash_changes_when_an_actual_seeded_row_changes_and_restores(self) -> None:
        original = collect_sales_mart_fingerprint(os.environ)
        connection = psycopg.connect(
            host=os.environ["POSTGRES_HOST"],
            port=int(os.environ["POSTGRES_PORT"]),
            dbname="chatbi_mvp",
            user=os.environ["POSTGRES_MIGRATOR_USER"],
            password=os.environ["POSTGRES_MIGRATOR_PASSWORD"],
            autocommit=True,
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT customer_name FROM mart_sales.dim_customer "
                    "WHERE customer_key = 1001"
                )
                original_name = cursor.fetchone()[0]
                cursor.execute(
                    "UPDATE mart_sales.dim_customer "
                    "SET customer_name = customer_name || ' fingerprint-test' "
                    "WHERE customer_key = 1001"
                )
            changed = collect_sales_mart_fingerprint(os.environ)
        finally:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE mart_sales.dim_customer SET customer_name = %s "
                    "WHERE customer_key = 1001",
                    (original_name,),
                )
            connection.close()

        restored = collect_sales_mart_fingerprint(os.environ)
        self.assertNotEqual(original.data_hash, changed.data_hash)
        self.assertEqual(original.data_hash, restored.data_hash)


def _connector(tables, *, seed="seed-v1"):
    return lambda **_: _FakeConnection(tables, seed=seed)


def _environment() -> dict[str, str]:
    return {
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "5433",
        "POSTGRES_DB": "chatbi_mvp",
        "POSTGRES_APP_USER": "chatbi_app",
        "POSTGRES_APP_PASSWORD": "local-test-password",
    }
