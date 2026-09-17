"""psycopg Database Adapter（数据库适配器）单元测试。"""

from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, call

from psycopg.errors import QueryCanceled

from src.online_query.contracts import ValidatedSQL
from src.online_query.database import (
    DatabaseError,
    DatabaseQueryTimeout,
    PsycopgQueryExecutor,
)


class DatabaseTest(unittest.TestCase):
    def test_from_env_uses_chatbi_app_and_safe_connection_options(self) -> None:
        connect = MagicMock()

        executor = PsycopgQueryExecutor.from_env(
            {
                "POSTGRES_HOST": "127.0.0.1",
                "POSTGRES_PORT": "5433",
                "POSTGRES_DB": "chatbi_mvp",
                "POSTGRES_APP_USER": "chatbi_app",
                "POSTGRES_APP_PASSWORD": "test-password",
            },
            connect=connect,
        )
        connection = MagicMock()
        connect.return_value.__enter__.return_value = connection
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.description = [SimpleNamespace(name="value")]
        cursor.fetchmany.return_value = [(1,)]

        executor.execute(ValidatedSQL("SELECT 1"))

        connect.assert_called_once_with(
            host="127.0.0.1",
            port=5433,
            dbname="chatbi_mvp",
            user="chatbi_app",
            password="test-password",
            connect_timeout=5,
            autocommit=True,
        )
        self.assertIs(connection.read_only, True)

    def test_rejects_missing_or_wrong_app_identity(self) -> None:
        base = {
            "POSTGRES_HOST": "127.0.0.1",
            "POSTGRES_PORT": "5433",
            "POSTGRES_DB": "chatbi_mvp",
            "POSTGRES_APP_USER": "chatbi_app",
            "POSTGRES_APP_PASSWORD": "test-password",
        }
        invalid = (
            {**base, "POSTGRES_APP_PASSWORD": ""},
            {**base, "POSTGRES_APP_USER": "postgres"},
            {**base, "POSTGRES_PORT": "invalid"},
        )

        for environ in invalid:
            with self.subTest(environ=environ):
                with self.assertRaises(DatabaseError):
                    PsycopgQueryExecutor.from_env(environ)

    def test_executes_read_only_with_timeout_and_empty_result(self) -> None:
        executor, connection, cursor = self._executor_with_cursor()
        cursor.description = [SimpleNamespace(name="order_id")]
        cursor.fetchmany.return_value = []

        result = executor.execute(
            ValidatedSQL(
                "SELECT order_id FROM mart_sales.fct_sales_order_line WHERE 1=0"
            )
        )

        self.assertIs(connection.read_only, True)
        connection.transaction.assert_called_once_with()
        cursor.execute.assert_has_calls(
            [
                call("SET LOCAL statement_timeout = '10s'"),
                call("SELECT order_id FROM mart_sales.fct_sales_order_line WHERE 1=0"),
            ]
        )
        cursor.fetchmany.assert_called_once_with(101)
        self.assertEqual(result.columns, ("order_id",))
        self.assertEqual(result.rows, ())
        self.assertFalse(result.truncated)

    def test_reads_101_rows_and_returns_first_100(self) -> None:
        executor, _, cursor = self._executor_with_cursor()
        cursor.description = [SimpleNamespace(name="number")]
        cursor.fetchmany.return_value = [(number,) for number in range(101)]

        result = executor.execute(ValidatedSQL("SELECT number FROM safe_table"))

        self.assertEqual(len(result.rows), 100)
        self.assertEqual(result.rows[0], (0,))
        self.assertEqual(result.rows[-1], (99,))
        self.assertTrue(result.truncated)

    def test_query_canceled_maps_to_query_timeout(self) -> None:
        executor, _, cursor = self._executor_with_cursor()
        cursor.execute.side_effect = [None, QueryCanceled("provider detail")]

        with self.assertRaisesRegex(DatabaseQueryTimeout, "超时") as raised:
            executor.execute(ValidatedSQL("SELECT 1"))

        self.assertIsInstance(raised.exception.__cause__, QueryCanceled)
        self.assertNotIn("provider detail", str(raised.exception))

    def test_other_database_error_is_controlled(self) -> None:
        connect = Mock(side_effect=RuntimeError("connection detail"))
        executor = PsycopgQueryExecutor(
            {
                "host": "127.0.0.1",
                "port": 5433,
                "dbname": "chatbi_mvp",
                "user": "chatbi_app",
                "password": "test-password",
            },
            connect=connect,
        )

        with self.assertRaisesRegex(DatabaseError, "连接或执行失败") as raised:
            executor.execute(ValidatedSQL("SELECT 1"))

        self.assertIsInstance(raised.exception.__cause__, RuntimeError)
        self.assertNotIn("connection detail", str(raised.exception))

    @staticmethod
    def _executor_with_cursor() -> tuple[
        PsycopgQueryExecutor,
        MagicMock,
        MagicMock,
    ]:
        connect = MagicMock()
        connection = MagicMock()
        connect.return_value.__enter__.return_value = connection
        cursor = connection.cursor.return_value.__enter__.return_value
        executor = PsycopgQueryExecutor(
            {
                "host": "127.0.0.1",
                "port": 5433,
                "dbname": "chatbi_mvp",
                "user": "chatbi_app",
                "password": "test-password",
            },
            connect=connect,
        )
        return executor, connection, cursor


if __name__ == "__main__":
    unittest.main()
