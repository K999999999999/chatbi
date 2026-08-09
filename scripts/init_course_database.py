"""初始化并验证第 4 课 PostgreSQL Course Baseline V1。

职责：
1. 在同一个 PostgreSQL 实例中创建独立 chatbi_mvp 数据库（如不存在）；
2. 按课程脚本顺序重建 public 下严格 5 张核心表；
3. 插入小规模课程仿真数据；
4. 执行 PostgreSQL 版 5 类课程验证 SQL；
5. 重新读取实际元数据，确认没有引入企业增强对象。

边界：不修改 .env，不修改当前 chatbi 数据库，不恢复 mart_sales，
不创建 Schema Catalog、RAG、Embedding、Metric 或 ChatBI 在线链路。
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql


ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "database" / "course_baseline"
DEFAULT_DATABASE = "chatbi_mvp"
EXPECTED_TABLES = {
    "dim_customers",
    "dim_products",
    "sales_orders",
    "exchange_rates",
    "finance_expenses",
}
FORBIDDEN_TABLES = {
    "dim_date",
    "dim_employee",
    "dim_currency",
    "dim_sales_territory",
}
FORBIDDEN_COLUMNS = {
    "sales_amount_cny",
    "gross_profit_cny",
    "gross_profit_amount_cny",
    "cost_amount_cny",
    "cost_cny",
    "exchange_rate_to_cny",
    "source_system",
    "source_id",
    "source_line_id",
    "dw_loaded_at",
    "etl_batch_id",
    "valid_from",
    "valid_to",
    "is_current",
    "created_at",
    "updated_at",
}
EXPECTED_COLUMNS = {
    "dim_customers": ["customer_id", "customer_name", "customer_type", "industry", "country", "region"],
    "dim_products": [
        "product_id", "product_name", "product_line", "category", "tech_route",
        "standard_cost", "material_cost", "labor_cost",
    ],
    "sales_orders": [
        "order_id", "order_no", "customer_id", "product_id", "region", "order_date",
        "order_status", "quantity", "unit_price", "discount_amount", "gross_amount",
        "net_amount", "currency",
    ],
    "exchange_rates": ["rate_date", "currency", "rate_to_cny"],
    "finance_expenses": [
        "expense_id", "expense_date", "department", "rd_expense", "selling_expense",
        "admin_expense", "finance_expense", "marketing_expense", "logistics_expense",
        "warranty_expense",
    ],
}


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def connection_config(env: dict[str, str], database: str) -> dict[str, Any]:
    required = ["POSTGRES_MIGRATOR_USER", "POSTGRES_MIGRATOR_PASSWORD"]
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise ValueError(f".env 缺少必要配置：{', '.join(missing)}")
    return {
        "host": env.get("POSTGRES_HOST", "127.0.0.1"),
        "port": int(env.get("POSTGRES_PORT", "5432")),
        "dbname": database,
        "user": env["POSTGRES_MIGRATOR_USER"],
        "password": env["POSTGRES_MIGRATOR_PASSWORD"],
        "connect_timeout": 10,
    }


def execute_sql_file(conn: psycopg.Connection[Any], file_name: str) -> None:
    """执行项目内课程 SQL；SQL 本身保持可人工审查和独立重跑。"""

    sql_text = (SQL_DIR / file_name).read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql_text)
    conn.commit()


def ensure_database(admin_config: dict[str, Any], database: str) -> bool:
    """创建独立课程数据库；返回本次是否新建。"""

    with psycopg.connect(**admin_config, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
            if cur.fetchone():
                return False
            cur.execute(sql.SQL("CREATE DATABASE {}\n").format(sql.Identifier(database)))
            return True


def normalize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    return value


def get_table_names(cur: Any) -> list[str]:
    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )
    return [row[0] for row in cur.fetchall()]


def get_columns(cur: Any, table: str) -> list[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table,),
    )
    return [row[0] for row in cur.fetchall()]


def run_validation(conn: psycopg.Connection[Any]) -> tuple[list[str], dict[str, int], dict[str, Any]]:
    """执行结构验证、五类课程查询和实际约束 introspection。"""

    errors: list[str] = []
    row_counts: dict[str, int] = {}
    validation_results: dict[str, Any] = {}
    with conn.cursor() as cur:
        actual_tables = get_table_names(cur)
        if set(actual_tables) != EXPECTED_TABLES:
            errors.append(f"public 表集合不一致：{actual_tables}")
        if len(actual_tables) != 5:
            errors.append(f"table_count 不是 5：{len(actual_tables)}")
        if FORBIDDEN_TABLES.intersection(actual_tables):
            errors.append(f"发现禁止表：{sorted(FORBIDDEN_TABLES.intersection(actual_tables))}")

        for table, expected_columns in EXPECTED_COLUMNS.items():
            actual_columns = get_columns(cur, table)
            if actual_columns != expected_columns:
                errors.append(f"字段集合或顺序不一致：{table} -> {actual_columns}")
            row_counts[table] = 0
            cur.execute(sql.SQL("SELECT COUNT(*) FROM public.{}\n").format(sql.Identifier(table)))
            row_counts[table] = int(cur.fetchone()[0])

        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND column_name = ANY(%s)
            """,
            (list(FORBIDDEN_COLUMNS),),
        )
        forbidden_columns_found = [row[0] for row in cur.fetchall()]
        if forbidden_columns_found:
            errors.append(f"发现禁止字段：{sorted(set(forbidden_columns_found))}")

        cur.execute(
            """
            SELECT conname, conrelid::regclass::text, contype, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE connamespace = 'public'::regnamespace
              AND conrelid::regclass::text NOT LIKE 'pg_%'
            ORDER BY conrelid::regclass::text, contype, conname
            """
        )
        constraints = cur.fetchall()
        validation_results["constraints"] = constraints
        pk_constraints = [row for row in constraints if row[2] == "p"]
        fk_constraints = [row for row in constraints if row[2] == "f"]
        unique_constraints = [row for row in constraints if row[2] == "u"]
        if len(pk_constraints) != 5:
            errors.append(f"PK 数量不符合课程模型：{len(pk_constraints)}")
        if len(fk_constraints) != 2:
            errors.append(f"FK 数量不符合课程模型：{len(fk_constraints)}")
        if not any("UNIQUE (order_no)" in row[3] for row in unique_constraints):
            errors.append("sales_orders.order_no UNIQUE 未发现")
        if not any("PRIMARY KEY (rate_date, currency)" in row[3] for row in pk_constraints):
            errors.append("exchange_rates 复合主键未发现")

        checks = {
            "customer_orphans": """
                SELECT COUNT(*) FROM public.sales_orders o
                LEFT JOIN public.dim_customers c ON c.customer_id = o.customer_id
                WHERE c.customer_id IS NULL
            """,
            "product_orphans": """
                SELECT COUNT(*) FROM public.sales_orders o
                LEFT JOIN public.dim_products p ON p.product_id = o.product_id
                WHERE p.product_id IS NULL
            """,
            "duplicate_order_no_groups": """
                SELECT COUNT(*) FROM (
                    SELECT order_no FROM public.sales_orders
                    GROUP BY order_no HAVING COUNT(*) > 1
                ) duplicates
            """,
            "missing_order_rates": """
                SELECT COUNT(*) FROM public.sales_orders o
                LEFT JOIN public.exchange_rates er
                  ON er.rate_date = o.order_date AND er.currency = o.currency
                WHERE er.currency IS NULL
            """,
            "cny_rate_errors": """
                SELECT COUNT(*) FROM public.exchange_rates
                WHERE currency = 'CNY' AND rate_to_cny <> 1
            """,
        }
        for name, query in checks.items():
            cur.execute(query)
            value = int(cur.fetchone()[0])
            validation_results[name] = value
            if value != 0:
                errors.append(f"{name}={value}")

        course_queries = {
            "验证1_订单状态": """
                SELECT order_status, COUNT(*) AS order_count, SUM(net_amount) AS total_net_amount
                FROM public.sales_orders
                GROUP BY order_status ORDER BY order_status
            """,
            "验证2_产品线收入": """
                SELECT p.product_line, COUNT(DISTINCT o.order_id) AS order_count,
                       SUM(o.quantity) AS total_quantity, SUM(o.net_amount) AS total_revenue
                FROM public.sales_orders o
                JOIN public.dim_products p ON o.product_id = p.product_id
                WHERE o.order_status = 'completed'
                GROUP BY p.product_line ORDER BY p.product_line
            """,
            "验证3_区域人民币收入": """
                SELECT c.region, ROUND(SUM(o.net_amount * er.rate_to_cny), 2) AS revenue_rmb,
                       COUNT(*) AS order_count
                FROM public.sales_orders o
                JOIN public.dim_customers c ON o.customer_id = c.customer_id
                JOIN public.exchange_rates er
                  ON o.order_date = er.rate_date AND o.currency = er.currency
                WHERE o.order_status = 'completed'
                GROUP BY c.region ORDER BY revenue_rmb DESC
            """,
            "验证4_产品线毛利": """
                SELECT p.product_line,
                       ROUND(SUM(o.net_amount), 2) AS revenue,
                       ROUND(SUM((p.material_cost + p.labor_cost) * o.quantity), 2) AS product_cost,
                       ROUND(SUM(o.net_amount - (p.material_cost + p.labor_cost) * o.quantity), 2) AS gross_profit,
                       ROUND(
                           SUM(o.net_amount - (p.material_cost + p.labor_cost) * o.quantity)
                           / NULLIF(SUM(o.net_amount), 0), 4
                       ) AS gross_margin_rate
                FROM public.sales_orders o
                JOIN public.dim_products p ON o.product_id = p.product_id
                WHERE o.order_status = 'completed'
                GROUP BY p.product_line ORDER BY p.product_line
            """,
            "验证5_月度费用": """
                SELECT date_trunc('month', expense_date)::DATE AS month,
                       SUM(rd_expense) AS total_rd,
                       SUM(selling_expense) AS total_selling,
                       SUM(admin_expense) AS total_admin,
                       SUM(finance_expense) AS total_finance
                FROM public.finance_expenses
                GROUP BY date_trunc('month', expense_date)::DATE
                ORDER BY month
            """,
        }
        for name, query in course_queries.items():
            cur.execute(query)
            validation_results[name] = [tuple(normalize(value) for value in row) for row in cur.fetchall()]
            if not validation_results[name]:
                errors.append(f"{name} 没有返回数据")

    return errors, row_counts, validation_results


def print_report(database_created: bool, row_counts: dict[str, int], results: dict[str, Any], errors: list[str]) -> None:
    print("=== Course Baseline V1 ===")
    print(f"database_created: {database_created}")
    print("database: chatbi_mvp")
    print("tables: dim_customers, dim_products, sales_orders, exchange_rates, finance_expenses")
    print(f"table_count: {len(row_counts)}")
    print("--- row counts ---")
    for table, count in row_counts.items():
        print(f"{table}: {count}")
    print("--- PK / FK / UNIQUE ---")
    for row in results["constraints"]:
        print(row)
    print("--- 5 course validations ---")
    for name in ("验证1_订单状态", "验证2_产品线收入", "验证3_区域人民币收入", "验证4_产品线毛利", "验证5_月度费用"):
        print(f"{name}: {results[name]}")
    print(f"validation_error_count: {len(errors)}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="初始化第 4 课 PostgreSQL Course Baseline V1")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    args = parser.parse_args()

    if args.database == "chatbi":
        raise SystemExit("拒绝将课程基线写入当前 chatbi；请使用独立数据库 chatbi_mvp。")

    env = load_env(args.env_file)
    admin_database = env.get("POSTGRES_DB", "postgres")
    admin_config = connection_config(env, admin_database)
    target_config = connection_config(env, args.database)

    try:
        database_created = ensure_database(admin_config, args.database)
        with psycopg.connect(**target_config) as conn:
            execute_sql_file(conn, "001_create_tables.sql")
            execute_sql_file(conn, "002_seed_course_data.sql")
            errors, row_counts, results = run_validation(conn)
            conn.commit()
        print_report(database_created, row_counts, results, errors)
        return 1 if errors else 0
    except (OSError, ValueError, psycopg.Error, RuntimeError) as exc:
        print(f"课程基线初始化失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

