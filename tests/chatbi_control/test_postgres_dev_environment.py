"""Integration checks for a freshly initialized local development PostgreSQL."""

import os
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import TypedDict
from unittest.mock import patch
from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from sqlalchemy import text

from src.business_analysis.run_store import (
    AnalysisRunConflict,
    AnalysisRunStatus,
    PostgresAnalysisRunStore,
)
from src.chatbi_control.database import (
    ControlDatabaseConfig,
    create_control_engine,
    verify_control_schema,
)


class _CheckpointState(TypedDict):
    value: int


@unittest.skipUnless(
    os.environ.get("RUN_DEVELOPMENT_DATABASE_TESTS") == "1",
    "run scripts/run_database_tests.py --profile development",
)
class PostgresDevelopmentEnvironmentTest(unittest.TestCase):
    @classmethod
    def _connect(
        cls,
        database: str,
        *,
        user_variable: str,
        password_variable: str,
    ) -> psycopg.Connection:
        return psycopg.connect(
            host=os.environ["POSTGRES_HOST"],
            port=int(os.environ["POSTGRES_PORT"]),
            dbname=database,
            user=os.environ[user_variable],
            password=os.environ[password_variable],
            connect_timeout=5,
        )

    def test_api_startup_uses_full_runtime_and_releases_analysis_thread(self) -> None:
        from src.query_api.main import app

        initial_threads = set(threading.enumerate())
        settings = {
            "CHATBI_ENV": "development",
            "CHATBI_ADMIN_SECRET_KEY": "test-admin-secret-32-characters-long",
            "LLM_API_KEY": "test-key",
            "LLM_MODEL": "test-model",
            "LLM_BASE_URL": "http://127.0.0.1:1/v1",
            "RAG_ONLINE_RETRIEVAL_ENABLED": "false",
            "CHATBI_OBSERVABILITY_ENABLED": "false",
            "CHATBI_TRACE_CONTENT_ENABLED": "false",
        }
        with patch.dict(os.environ, settings):
            with TestClient(app) as client:
                self.assertEqual(client.get("/health").status_code, 200)
                self.assertEqual(
                    client.get("/admin/", follow_redirects=False).status_code, 302
                )
                self.assertEqual(client.post("/api/v1/query", json={}).status_code, 400)
                self.assertIsNotNone(app.state.analysis_service)
            self.assertIsNone(app.state.query_service)
            self.assertIsNone(app.state.analysis_service)
        remaining = set(threading.enumerate()) - initial_threads
        self.assertFalse(
            any(
                thread.name == "business-analysis-checkpoint-cleanup"
                for thread in remaining
            )
        )

    def test_synthetic_seed_covers_dates_dimensions_statuses_and_metrics(self) -> None:
        with (
            self._connect(
                "chatbi_mvp",
                user_variable="POSTGRES_APP_USER",
                password_variable="POSTGRES_APP_PASSWORD",
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "SELECT seed_version FROM mart_sales.dev_seed_metadata WHERE singleton"
            )
            self.assertEqual(cursor.fetchone(), ("chatbi-sales-mart-dev-v3",))

            cursor.execute(
                """
                    SELECT min(year), max(year), count(DISTINCT year),
                           count(DISTINCT quarter), count(DISTINCT month),
                           count(DISTINCT full_date)
                    FROM mart_sales.dim_date
                    """
            )
            self.assertEqual(cursor.fetchone(), (2024, 2025, 2, 4, 12, 731))

            cursor.execute(
                """
                    SELECT count(*), count(DISTINCT order_id),
                           count(*) FILTER (WHERE order_status = 'completed'),
                           count(*) FILTER (WHERE order_status = 'confirmed'),
                           count(*) FILTER (WHERE order_status = 'pending'),
                           count(*) FILTER (WHERE order_status = 'cancelled'),
                           count(DISTINCT transaction_currency_key)
                    FROM mart_sales.fct_sales_order_line
                    """
            )
            (
                line_count,
                order_count,
                completed,
                confirmed,
                pending,
                cancelled,
                currencies,
            ) = cursor.fetchone()
            self.assertGreater(line_count, 1000)
            self.assertGreater(order_count, 400)
            self.assertGreater(completed, 0)
            self.assertGreater(confirmed, 0)
            self.assertGreater(pending, 0)
            self.assertGreater(cancelled, 0)
            self.assertEqual(currencies, 4)

            cursor.execute(
                """
                    SELECT count(*) FILTER (WHERE order_line_count > 1),
                           count(DISTINCT customer.customer_type),
                           count(DISTINCT product.product_line),
                           count(DISTINCT region.sales_region_key),
                           count(DISTINCT (customer.customer_region, region.sales_region_key))
                    FROM (
                        SELECT order_id, count(*) AS order_line_count
                        FROM mart_sales.fct_sales_order_line
                        GROUP BY order_id
                    ) AS order_counts
                    JOIN mart_sales.fct_sales_order_line AS fact USING (order_id)
                    JOIN mart_sales.dim_customer AS customer
                      ON customer.customer_key = fact.customer_key
                    JOIN mart_sales.dim_product AS product
                      ON product.product_key = fact.product_key
                    JOIN mart_sales.dim_sales_region AS region
                      ON region.sales_region_key = fact.sales_region_key
                    """
            )
            (
                multi_line_orders,
                customer_types,
                product_lines,
                sales_regions,
                region_pairs,
            ) = cursor.fetchone()
            self.assertGreater(multi_line_orders, 0)
            self.assertEqual(customer_types, 3)
            self.assertGreaterEqual(product_lines, 4)
            self.assertEqual(sales_regions, 6)
            self.assertGreater(region_pairs, sales_regions)

            cursor.execute(
                """
                    SELECT count(DISTINCT (date_row.year, date_row.quarter)),
                           count(DISTINCT date_trunc('month', date_row.full_date)),
                           count(DISTINCT date_row.full_date)
                    FROM mart_sales.fct_sales_order_line AS fact
                    JOIN mart_sales.dim_date AS date_row
                      ON date_row.date_key = fact.completion_date_key
                    WHERE fact.order_status = 'completed'
                    """
            )
            quarters, months, completion_days = cursor.fetchone()
            self.assertEqual(quarters, 8)
            self.assertGreaterEqual(months, 24)
            self.assertGreater(completion_days, 300)

            cursor.execute(
                """
                    SELECT sum(net_sales_amount_cny),
                           sum(sales_cost_amount_cny),
                           sum(net_sales_amount_cny - sales_cost_amount_cny),
                           sum(net_sales_amount_cny - sales_cost_amount_cny)
                               / NULLIF(sum(net_sales_amount_cny), 0)
                    FROM mart_sales.fct_sales_order_line
                    WHERE order_status = 'completed'
                    """
            )
            sales, cost, profit, margin = cursor.fetchone()
            self.assertGreater(sales, cost)
            self.assertGreater(cost, 0)
            self.assertGreater(profit, 0)
            self.assertGreater(margin, 0)
            self.assertLess(margin, 1)

            cursor.execute(
                """
                    SELECT count(*)
                    FROM mart_sales.fct_sales_order_line
                    WHERE order_status = 'completed'
                      AND net_sales_amount_cny = 0
                    """
            )
            self.assertGreater(cursor.fetchone()[0], 0)
            cursor.execute(
                """
                    SELECT sum(net_sales_amount_cny - sales_cost_amount_cny)
                           / NULLIF(sum(net_sales_amount_cny), 0)
                    FROM mart_sales.fct_sales_order_line
                    WHERE order_status = 'completed'
                      AND net_sales_amount_cny = 0
                    """
            )
            self.assertIsNone(cursor.fetchone()[0])

            cursor.execute(
                """
                    SELECT count(*)
                    FROM (
                        SELECT date_row.year, region.sales_region_name,
                               product.product_line,
                               sum(fact.net_sales_amount_cny) AS sales
                        FROM mart_sales.fct_sales_order_line AS fact
                        JOIN mart_sales.dim_date AS date_row
                          ON date_row.date_key = fact.completion_date_key
                        JOIN mart_sales.dim_sales_region AS region
                          ON region.sales_region_key = fact.sales_region_key
                        JOIN mart_sales.dim_product AS product
                          ON product.product_key = fact.product_key
                        WHERE fact.order_status = 'completed'
                        GROUP BY date_row.year, region.sales_region_name,
                                 product.product_line
                        HAVING sum(fact.net_sales_amount_cny) > 0
                    ) AS grouped_sales
                    """
            )
            self.assertGreater(cursor.fetchone()[0], 20)

    def test_sales_mart_descriptions_are_installed_in_postgres_catalog(self) -> None:
        with (
            self._connect(
                "chatbi_mvp",
                user_variable="POSTGRES_APP_USER",
                password_variable="POSTGRES_APP_PASSWORD",
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                """
                    SELECT
                        count(*) FILTER (WHERE description.objsubid = 0),
                        count(*) FILTER (WHERE description.objsubid > 0)
                    FROM pg_catalog.pg_description AS description
                    JOIN pg_catalog.pg_class AS catalog_relation
                      ON catalog_relation.oid = description.objoid
                    JOIN pg_catalog.pg_namespace AS catalog_namespace
                      ON catalog_namespace.oid = catalog_relation.relnamespace
                    WHERE catalog_namespace.nspname = 'mart_sales'
                    """
            )
            self.assertEqual(cursor.fetchone(), (7, 69))

    def test_sales_mart_account_is_read_only(self) -> None:
        with (
            self._connect(
                "chatbi_mvp",
                user_variable="POSTGRES_APP_USER",
                password_variable="POSTGRES_APP_PASSWORD",
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                """
                    SELECT current_user,
                           has_database_privilege(current_user, current_database(), 'CONNECT'),
                           has_database_privilege(current_user, 'chatbi_control', 'CONNECT'),
                           has_database_privilege(current_user, 'postgres', 'CONNECT'),
                           has_table_privilege(current_user,
                             'mart_sales.fct_sales_order_line', 'SELECT'),
                           has_table_privilege(current_user,
                             'mart_sales.fct_sales_order_line', 'INSERT'),
                           has_table_privilege(current_user,
                             'mart_sales.fct_sales_order_line', 'UPDATE'),
                           has_table_privilege(current_user,
                             'mart_sales.fct_sales_order_line', 'DELETE')
                    """
            )
            self.assertEqual(
                cursor.fetchone(),
                ("chatbi_app", True, False, False, True, False, False, False),
            )

    def test_control_schema_rbac_and_runtime_permissions_are_initialized_without_admin(
        self,
    ) -> None:
        config = ControlDatabaseConfig.from_environment(require_migrator=False)
        engine = create_control_engine(config)
        try:
            verify_control_schema(engine)
        finally:
            engine.dispose()

        with (
            self._connect(
                "chatbi_control",
                user_variable="POSTGRES_CONTROL_APP_USER",
                password_variable="POSTGRES_CONTROL_APP_PASSWORD",
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute("SELECT version FROM schema_migrations")
            self.assertEqual(
                set(cursor.fetchall()),
                {
                    ("chatbi-control-v1",),
                    ("chatbi-control-v2",),
                    ("chatbi-control-v3",),
                },
            )
            cursor.execute(
                """
                    SELECT role.name, count(role_permission.permission_id)
                    FROM roles AS role
                    LEFT JOIN role_permissions AS role_permission
                      ON role_permission.role_id = role.id
                    GROUP BY role.name
                    ORDER BY role.name
                    """
            )
            self.assertEqual(cursor.fetchall(), [("admin", 4), ("analyst", 1)])

            cursor.execute("SELECT count(*) FROM users")
            self.assertEqual(cursor.fetchone(), (0,))

            cursor.execute(
                """
                    SELECT current_user,
                           has_database_privilege(current_user, 'chatbi_control', 'CONNECT'),
                           has_database_privilege(current_user, 'chatbi_mvp', 'CONNECT'),
                           has_database_privilege(current_user, 'postgres', 'CONNECT'),
                           has_table_privilege(current_user, 'users', 'INSERT'),
                           has_table_privilege(current_user, 'users', 'DELETE'),
                           has_table_privilege(current_user, 'permissions', 'UPDATE'),
                           (SELECT rolsuper FROM pg_roles WHERE rolname = current_user),
                           (SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user),
                           (SELECT rolcreaterole FROM pg_roles WHERE rolname = current_user)
                    """
            )
            self.assertEqual(
                cursor.fetchone(),
                (
                    "chatbi_control_user",
                    True,
                    False,
                    False,
                    True,
                    False,
                    False,
                    False,
                    False,
                    False,
                ),
            )

        with (
            self._connect(
                "chatbi_control",
                user_variable="POSTGRES_MIGRATOR_USER",
                password_variable="POSTGRES_MIGRATOR_PASSWORD",
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                """
                    SELECT to_regclass('public.checkpoints') IS NOT NULL,
                           to_regclass('public.checkpoint_blobs') IS NOT NULL,
                           to_regclass('public.checkpoint_writes') IS NOT NULL,
                           to_regclass('public.checkpoint_migrations') IS NOT NULL,
                           EXISTS (SELECT 1 FROM checkpoint_migrations)
                    """
            )
            self.assertEqual(cursor.fetchone(), (True, True, True, True, True))

    def test_analysis_runs_are_owner_bound_checkpointed_and_expired(self) -> None:
        config = ControlDatabaseConfig.from_environment(require_migrator=False)
        engine = create_control_engine(config)
        pool = ConnectionPool(
            make_conninfo(**config.app_connection_kwargs()),
            kwargs={"autocommit": True, "row_factory": dict_row},
            min_size=1,
            max_size=2,
            open=True,
        )
        run_store = PostgresAnalysisRunStore(engine)
        run_id = uuid4()
        expired_id = uuid4()
        question = "2025年3月毛利为什么比2月下降？"
        try:
            saver = PostgresSaver(pool)
            builder = StateGraph(_CheckpointState)
            builder.add_node("save", lambda state: {"value": state["value"] + 1})
            builder.add_edge(START, "save")
            builder.add_edge("save", END)
            graph = builder.compile(checkpointer=saver)
            graph.invoke(
                {"value": 1},
                config={"configurable": {"thread_id": str(expired_id)}},
            )

            first = run_store.claim(
                run_id,
                owner_subject="test:user-1",
                question=question,
            )
            self.assertEqual(first.status, AnalysisRunStatus.NEW)
            resumed = run_store.claim(
                run_id,
                owner_subject="test:user-1",
                question=question,
            )
            self.assertEqual(resumed.status, AnalysisRunStatus.ACTIVE)
            with self.assertRaises(AnalysisRunConflict) as owner_error:
                run_store.claim(
                    run_id,
                    owner_subject="test:user-2",
                    question=question,
                )
            self.assertEqual(
                owner_error.exception.reason,
                "ANALYSIS_RUN_OWNER_MISMATCH",
            )
            with self.assertRaises(AnalysisRunConflict) as question_error:
                run_store.claim(
                    run_id,
                    owner_subject="test:user-1",
                    question="另一问题",
                )
            self.assertEqual(
                question_error.exception.reason,
                "ANALYSIS_RUN_QUESTION_MISMATCH",
            )
            run_store.mark_completed(run_id)
            completed = run_store.claim(
                run_id,
                owner_subject="test:user-1",
                question=question,
            )
            self.assertEqual(completed.status, AnalysisRunStatus.COMPLETED)

            run_store.claim(
                expired_id,
                owner_subject="test:user-1",
                question=question,
            )
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE business_analysis_runs SET expires_at = :expired "
                        "WHERE analysis_run_id = :run_id"
                    ),
                    {
                        "expired": datetime.now(UTC) - timedelta(seconds=1),
                        "run_id": str(expired_id),
                    },
                )
            self.assertEqual(run_store.cleanup_expired(), 1)
            with self.assertRaises(AnalysisRunConflict) as expired_error:
                run_store.claim(
                    expired_id,
                    owner_subject="test:user-1",
                    question=question,
                )
            self.assertEqual(
                expired_error.exception.reason,
                "ANALYSIS_RUN_EXPIRED",
            )
            snapshot = graph.get_state({"configurable": {"thread_id": str(expired_id)}})
            self.assertEqual(snapshot.values, {})
        finally:
            pool.close()
            engine.dispose()

    def test_reapplying_seed_preserves_the_same_data_summary(self) -> None:
        with self._connect(
            "chatbi_mvp",
            user_variable="POSTGRES_MIGRATOR_USER",
            password_variable="POSTGRES_MIGRATOR_PASSWORD",
        ) as connection:
            before = self._seed_summary(connection)
            root = Path(__file__).resolve().parents[2]
            seed_sql = (root / "database" / "dev" / "seed_sales_mart.sql").read_text(
                encoding="utf-8"
            )
            with connection.transaction():
                connection.execute(seed_sql, prepare=False)
            self.assertEqual(self._seed_summary(connection), before)

    def test_migration_does_not_create_admin_and_explicit_admin_is_one_time(
        self,
    ) -> None:
        from src.authorization.passwords import verify_password
        from src.bootstrap.commands import main

        with (
            self._connect(
                "chatbi_control",
                user_variable="POSTGRES_CONTROL_APP_USER",
                password_variable="POSTGRES_CONTROL_APP_PASSWORD",
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute("SELECT count(*) FROM users")
            self.assertEqual(cursor.fetchone(), (0,))

        migration_stdout = StringIO()
        migration_stderr = StringIO()
        with redirect_stdout(migration_stdout), redirect_stderr(migration_stderr):
            self.assertEqual(main(["migrate"]), 0)
        self.assertIn("没有创建管理员", migration_stdout.getvalue())

        with (
            self._connect(
                "chatbi_control",
                user_variable="POSTGRES_CONTROL_APP_USER",
                password_variable="POSTGRES_CONTROL_APP_PASSWORD",
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute("SELECT count(*) FROM users")
            self.assertEqual(cursor.fetchone(), (0,))

        admin_password = "temporary-admin-password-123"
        admin_stdout = StringIO()
        admin_stderr = StringIO()
        with (
            patch(
                "src.bootstrap.control.getpass.getpass",
                side_effect=[admin_password, admin_password],
            ),
            redirect_stdout(admin_stdout),
            redirect_stderr(admin_stderr),
        ):
            self.assertEqual(main(["create-admin", "--username", "admin-1"]), 0)
        self.assertNotIn(
            admin_password, admin_stdout.getvalue() + admin_stderr.getvalue()
        )

        with (
            self._connect(
                "chatbi_control",
                user_variable="POSTGRES_CONTROL_APP_USER",
                password_variable="POSTGRES_CONTROL_APP_PASSWORD",
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                """
                    SELECT users.username, users.is_active,
                           users.must_change_password, users.password_hash
                    FROM users
                    JOIN user_roles ON user_roles.user_id = users.id
                    JOIN roles ON roles.id = user_roles.role_id
                    WHERE roles.name = 'admin'
                    """
            )
            saved_admin = cursor.fetchone()
            self.assertEqual(saved_admin[:3], ("admin-1", True, True))
            self.assertTrue(verify_password(admin_password, saved_admin[3]))
            cursor.execute("SELECT count(*) FROM users")
            self.assertEqual(cursor.fetchone(), (1,))

        duplicate_stdout = StringIO()
        duplicate_stderr = StringIO()
        with (
            patch(
                "src.bootstrap.control.getpass.getpass",
                side_effect=[
                    "another-admin-password-123",
                    "another-admin-password-123",
                ],
            ),
            redirect_stdout(duplicate_stdout),
            redirect_stderr(duplicate_stderr),
        ):
            self.assertEqual(main(["create-admin", "--username", "admin-2"]), 1)
        duplicate_output = duplicate_stdout.getvalue() + duplicate_stderr.getvalue()
        self.assertNotIn("another-admin-password-123", duplicate_output)
        self.assertIn("首个管理员已经初始化", duplicate_output)

        with (
            self._connect(
                "chatbi_control",
                user_variable="POSTGRES_CONTROL_APP_USER",
                password_variable="POSTGRES_CONTROL_APP_PASSWORD",
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute("SELECT count(*) FROM users")
            self.assertEqual(cursor.fetchone(), (1,))

    @staticmethod
    def _seed_summary(connection: psycopg.Connection) -> tuple[object, ...]:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    (SELECT count(*) FROM mart_sales.dim_date),
                    (SELECT count(*) FROM mart_sales.dim_customer),
                    (SELECT count(*) FROM mart_sales.dim_product),
                    (SELECT count(*) FROM mart_sales.dim_sales_region),
                    (SELECT count(*) FROM mart_sales.dim_currency),
                    (SELECT count(*) FROM mart_sales.fct_exchange_rate_daily),
                    (SELECT count(*) FROM mart_sales.fct_sales_order_line),
                    (SELECT count(DISTINCT order_id)
                     FROM mart_sales.fct_sales_order_line),
                    (SELECT sum(net_sales_amount_cny)
                     FROM mart_sales.fct_sales_order_line
                     WHERE order_status = 'completed'),
                    (SELECT sum(sales_cost_amount_cny)
                     FROM mart_sales.fct_sales_order_line
                     WHERE order_status = 'completed'),
                    (SELECT seed_version
                     FROM mart_sales.dev_seed_metadata
                     WHERE singleton)
                """
            )
            return cursor.fetchone()
