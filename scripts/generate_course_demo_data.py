"""生成 Course Baseline V1 的确定性大规模仿真数据。

职责：只清空并批量写入 chatbi_mvp 的现有 5 张课程表，不修改表结构。
数据粒度：sales_orders 仍然是一行一条销售订单，不引入订单头明细模型。
安全边界：target_database 不是 chatbi_mvp 时立即停止；不会 DROP TABLE。
"""

from __future__ import annotations

import argparse
import calendar
import math
import random
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable

import psycopg

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.init_course_database import (  # noqa: E402
    EXPECTED_COLUMNS,
    EXPECTED_TABLES,
    connection_config,
    load_env,
)


DATABASE_NAME = "chatbi_mvp"
DEFAULT_SEED = 42
DEFAULT_CUSTOMER_COUNT = 500
DEFAULT_PRODUCT_COUNT = 150
DEFAULT_ORDER_COUNT = 30_000
DEFAULT_START_DATE = date(2024, 1, 1)
DEFAULT_END_DATE = date(2026, 12, 31)
MONEY = Decimal("0.01")
RATE = Decimal("0.0001")

REGIONS = ["欧洲", "北美", "亚太"]
COUNTRIES_BY_REGION = {
    "欧洲": ["Germany", "France", "Spain", "UK", "Italy", "Netherlands"],
    "北美": ["USA", "Canada", "Mexico"],
    "亚太": ["China", "Japan", "South Korea", "Australia", "Singapore"],
}
CUSTOMER_TYPES = ["OEM整车厂", "储能集成商", "电网集团", "工商业用户", "换电运营商", "经销商"]
CUSTOMER_TYPE_WEIGHTS = [0.25, 0.20, 0.12, 0.15, 0.08, 0.20]
INDUSTRIES = ["交通", "能源", "工业", "特种交通"]
INDUSTRY_WEIGHTS_BY_TYPE = {
    "OEM整车厂": [0.78, 0.05, 0.05, 0.12],
    "储能集成商": [0.05, 0.60, 0.28, 0.07],
    "电网集团": [0.02, 0.86, 0.10, 0.02],
    "工商业用户": [0.08, 0.35, 0.50, 0.07],
    "换电运营商": [0.52, 0.18, 0.10, 0.20],
    "经销商": [0.35, 0.25, 0.30, 0.10],
}

PRODUCT_LINE_SPECS = {
    "动力电池-乘用车": {
        "categories": ["高能量密度型", "超快充型", "低温适配型"],
        "routes": ["三元锂", "磷酸铁锂", "固态电池", "钠离子"],
        "route_weights": [0.42, 0.30, 0.18, 0.10],
        "base_cost": 950,
        "quantity": (80, 650),
    },
    "动力电池-商用车": {
        "categories": ["商用车标准型", "超快充型", "低温适配型"],
        "routes": ["磷酸铁锂", "钠离子", "三元锂"],
        "route_weights": [0.58, 0.24, 0.18],
        "base_cost": 760,
        "quantity": (60, 360),
    },
    "储能系统-电网级": {
        "categories": ["电网级储能型"],
        "routes": ["磷酸铁锂", "钠离子", "固态电池"],
        "route_weights": [0.58, 0.28, 0.14],
        "base_cost": 280_000,
        "quantity": (1, 8),
    },
    "储能系统-工商业": {
        "categories": ["工商业储能型", "低温适配型"],
        "routes": ["磷酸铁锂", "钠离子", "固态电池"],
        "route_weights": [0.48, 0.27, 0.25],
        "base_cost": 115_000,
        "quantity": (2, 24),
    },
    "电池材料与回收": {
        "categories": ["回收处理型", "材料组件型"],
        "routes": ["钠离子", "磷酸铁锂", "固态电池"],
        "route_weights": [0.48, 0.37, 0.15],
        "base_cost": 14_000,
        "quantity": (20, 300),
    },
}
PRODUCT_LINES = list(PRODUCT_LINE_SPECS)
BASE_PRODUCT_LINE_WEIGHTS = [0.30, 0.18, 0.22, 0.20, 0.10]
TECH_ROUTE_COST_MULTIPLIER = {
    "三元锂": Decimal("1.15"),
    "磷酸铁锂": Decimal("0.96"),
    "钠离子": Decimal("0.88"),
    "固态电池": Decimal("1.38"),
}
TECH_ROUTE_MARKUP = {
    "三元锂": Decimal("1.84"),
    "磷酸铁锂": Decimal("1.76"),
    "钠离子": Decimal("1.68"),
    "固态电池": Decimal("1.48"),
}
TAX_RATE_BY_LINE = {
    "动力电池-乘用车": Decimal("0.13"),
    "动力电池-商用车": Decimal("0.13"),
    "储能系统-电网级": Decimal("0.13"),
    "储能系统-工商业": Decimal("0.13"),
    "电池材料与回收": Decimal("0.09"),
}
STATUS_BY_YEAR = {
    2024: (["completed", "pending", "cancelled"], [0.74, 0.15, 0.11]),
    2025: (["completed", "pending", "cancelled"], [0.78, 0.13, 0.09]),
    2026: (["completed", "pending", "cancelled"], [0.81, 0.12, 0.07]),
}
CURRENCY_WEIGHTS_BY_REGION = {
    # 保留跨币种结算，同时让总体分布接近课程要求的 CNY 50%~60%、
    # USD 20%~30%、EUR 15%~25%。
    "欧洲": (["CNY", "USD", "EUR"], [0.30, 0.08, 0.62]),
    "北美": (["CNY", "USD", "EUR"], [0.30, 0.62, 0.08]),
    "亚太": (["CNY", "USD", "EUR"], [0.90, 0.06, 0.04]),
}
REGION_WEIGHTS_BY_YEAR = {
    2024: [0.40, 0.30, 0.30],
    2025: [0.35, 0.32, 0.33],
    2026: [0.28, 0.28, 0.44],
}
MONTH_WEIGHTS = [0.92, 0.82, 0.98, 1.00, 1.02, 0.96, 0.90, 0.94, 1.04, 1.10, 1.20, 1.25]
QUARTER_MONTHS = {1: [1, 2, 3], 2: [4, 5, 6], 3: [7, 8, 9], 4: [10, 11, 12]}


def q2(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def q4(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(RATE, rounding=ROUND_HALF_UP)


def weighted_choice(rng: random.Random, values: list[Any], weights: list[float]) -> Any:
    return rng.choices(values, weights=weights, k=1)[0]


def daterange(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def month_start(value: date) -> date:
    return value.replace(day=1)


def choose_order_date(rng: random.Random, start: date, end: date) -> date:
    years = list(range(start.year, end.year + 1))
    year_weights = [0.25, 0.33, 0.42][: len(years)]
    year = weighted_choice(rng, years, year_weights)
    quarter = weighted_choice(rng, [1, 2, 3, 4], [0.22, 0.23, 0.24, 0.31])
    months = QUARTER_MONTHS[quarter]
    month_weights = [MONTH_WEIGHTS[month - 1] for month in months]
    month = weighted_choice(rng, months, month_weights)
    day = rng.randint(1, calendar.monthrange(year, month)[1])
    selected = date(year, month, day)
    if selected < start:
        return start
    if selected > end:
        return end
    return selected


def exchange_rate(rate_date: date, currency: str) -> Decimal:
    """生成平滑的 CNY/外币汇率，不复制真实历史数据。"""

    if currency == "CNY":
        return Decimal("1.0000")
    day_index = (rate_date - DEFAULT_START_DATE).days
    trend = Decimal(day_index) / Decimal("1095")
    seasonal = Decimal(str(math.sin(day_index / 38.0))) * Decimal("0.028")
    weekly = Decimal(str(math.sin(day_index / 9.0))) * Decimal("0.006")
    if currency == "USD":
        return q4(Decimal("7.1200") + trend * Decimal("0.1200") + seasonal + weekly)
    return q4(Decimal("7.7600") - trend * Decimal("0.0800") + seasonal * Decimal("1.2") + weekly)


def generate_customers(rng: random.Random, count: int) -> tuple[list[tuple[Any, ...]], list[dict[str, Any]]]:
    rows: list[tuple[Any, ...]] = []
    metadata: list[dict[str, Any]] = []
    for customer_id in range(1, count + 1):
        region = rng.choice(REGIONS)
        country = rng.choice(COUNTRIES_BY_REGION[region])
        customer_type = weighted_choice(rng, CUSTOMER_TYPES, CUSTOMER_TYPE_WEIGHTS)
        industry = weighted_choice(rng, INDUSTRIES, INDUSTRY_WEIGHTS_BY_TYPE[customer_type])
        name_prefix = {"欧洲": "欧洲", "北美": "北美", "亚太": "亚太"}[region]
        name = f"{name_prefix}{customer_type}模拟客户{customer_id:04d}"
        rows.append((customer_id, name, customer_type, industry, country, region))
        metadata.append({
            "customer_id": customer_id,
            "customer_type": customer_type,
            "industry": industry,
            "country": country,
            "region": region,
        })
    return rows, metadata


def generate_products(rng: random.Random, count: int) -> tuple[list[tuple[Any, ...]], list[dict[str, Any]]]:
    rows: list[tuple[Any, ...]] = []
    metadata: list[dict[str, Any]] = []
    for product_id in range(1, count + 1):
        line = weighted_choice(rng, PRODUCT_LINES, BASE_PRODUCT_LINE_WEIGHTS)
        spec = PRODUCT_LINE_SPECS[line]
        category = rng.choice(spec["categories"])
        route = weighted_choice(rng, spec["routes"], spec["route_weights"])
        route_multiplier = TECH_ROUTE_COST_MULTIPLIER[route]
        base_cost = Decimal(str(spec["base_cost"])) * route_multiplier
        standard_cost = q2(base_cost * Decimal(str(rng.uniform(0.82, 1.18))))
        material_share = Decimal(str(rng.uniform(0.58, 0.74)))
        material_cost = q2(standard_cost * material_share * Decimal(str(rng.uniform(0.94, 1.05))))
        labor_cost = q2(standard_cost * (Decimal("1") - material_share) * Decimal(str(rng.uniform(0.86, 1.10))))
        if material_cost <= 0 or labor_cost <= 0 or standard_cost <= 0:
            raise RuntimeError("产品成本必须为正")
        product_name = f"{category}-{route}-仿真产品{product_id:04d}"
        rows.append((
            product_id, product_name, line, category, route,
            standard_cost, material_cost, labor_cost,
        ))
        metadata.append({
            "product_id": product_id,
            "product_line": line,
            "category": category,
            "tech_route": route,
            "standard_cost": standard_cost,
            "material_cost": material_cost,
            "labor_cost": labor_cost,
            "price_cny": q2(standard_cost * TECH_ROUTE_MARKUP[route] * Decimal(str(rng.uniform(0.94, 1.08)))),
        })
    return rows, metadata


def product_line_weights(year: int, quarter: int) -> list[float]:
    weights = BASE_PRODUCT_LINE_WEIGHTS.copy()
    if year == 2026 and quarter == 2:
        # 场景 B：商用车业务需求压力；同时把部分机会转移到储能业务。
        weights[1] = 0.19
        weights[2] = 0.27
        weights[3] = 0.23
    elif year == 2026 and quarter == 3:
        # 场景 C：高成本储能组合占比上升。
        weights[1] = 0.15
        weights[2] = 0.27
        weights[3] = 0.23
    return weights


def choose_product(rng: random.Random, products: list[dict[str, Any]], year: int, quarter: int) -> dict[str, Any]:
    weights: list[float] = []
    for product in products:
        line_factor = product_line_weights(year, quarter)[PRODUCT_LINES.index(product["product_line"])]
        if year in (2026,) and quarter in (2, 3) and product["tech_route"] == "固态电池":
            line_factor *= 4.0
        weights.append(line_factor)
    return weighted_choice(rng, products, weights)


def choose_quantity(rng: random.Random, product: dict[str, Any], year: int, quarter: int) -> Decimal:
    low, high = PRODUCT_LINE_SPECS[product["product_line"]]["quantity"]
    quantity = Decimal(str(rng.uniform(low, high)))
    if year == 2026 and quarter == 2 and product["product_line"] == "动力电池-商用车":
        # 场景 B：通过订单数量收缩表达商用车业务收入下降。
        quantity *= Decimal("0.98")
    return q2(quantity)


def choose_sales_region(rng: random.Random, customer_region: str) -> str:
    if rng.random() < 0.88:
        return customer_region
    return rng.choice([region for region in REGIONS if region != customer_region])


def choose_currency(rng: random.Random, customer_region: str) -> str:
    values, weights = CURRENCY_WEIGHTS_BY_REGION[customer_region]
    return weighted_choice(rng, values, weights)


def generate_orders(
    rng: random.Random,
    customers: list[dict[str, Any]],
    products: list[dict[str, Any]],
    count: int,
    start: date,
    end: date,
    rate_map: dict[tuple[date, str], Decimal],
) -> tuple[list[tuple[Any, ...]], dict[str, Any]]:
    rows: list[tuple[Any, ...]] = []
    distributions: dict[str, Counter[str]] = {
        "status": Counter(),
        "currency": Counter(),
        "customer_region": Counter(),
        "sales_region": Counter(),
        "product_line": Counter(),
    }
    customers_by_region: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for customer in customers:
        customers_by_region[customer["region"]].append(customer)

    for order_id in range(1, count + 1):
        order_date = choose_order_date(rng, start, end)
        year = order_date.year
        quarter = (order_date.month - 1) // 3 + 1
        customer_region = weighted_choice(rng, REGIONS, REGION_WEIGHTS_BY_YEAR[year])
        customer = rng.choice(customers_by_region[customer_region])
        sales_region = choose_sales_region(rng, customer_region)
        currency = choose_currency(rng, customer_region)
        status_values, status_weights = STATUS_BY_YEAR[year]
        status = weighted_choice(rng, status_values, status_weights)
        product = choose_product(rng, products, year, quarter)
        quantity = choose_quantity(rng, product, year, quarter)
        rate = rate_map[(order_date, currency)]
        unit_price_cny = product["price_cny"]
        # 课程模型没有产品成本币种字段，且原课程毛利 SQL 直接比较
        # net_amount 与 material_cost + labor_cost。订单金额采用统一的
        # 课程数值口径，避免外币订单在原课程 SQL 中被错误放大成本差异；
        # currency 与 exchange_rates 仍用于人民币收入换算验证。
        unit_price = q2(unit_price_cny)
        base_amount = q2(quantity * unit_price)
        discount_base = {"OEM整车厂": 0.10, "储能集成商": 0.07, "电网集团": 0.05, "工商业用户": 0.06, "换电运营商": 0.08, "经销商": 0.12}[customer["customer_type"]]
        discount_rate = Decimal(str(max(0.0, min(0.20, rng.gauss(discount_base, 0.025)))))
        discount_amount = q2(base_amount * discount_rate)
        net_amount = q2(base_amount - discount_amount)
        tax_rate = TAX_RATE_BY_LINE[product["product_line"]]
        gross_amount = q2(net_amount * (Decimal("1") + tax_rate))
        if quantity <= 0 or unit_price <= 0 or discount_amount < 0 or net_amount <= 0 or gross_amount < net_amount:
            raise RuntimeError("订单金额或数量生成违反课程约束")
        rows.append((
            order_id,
            f"SO{order_date.strftime('%Y%m')}{order_id:06d}",
            customer["customer_id"],
            product["product_id"],
            sales_region,
            order_date,
            status,
            quantity,
            unit_price,
            discount_amount,
            gross_amount,
            net_amount,
            currency,
        ))
        distributions["status"][status] += 1
        distributions["currency"][currency] += 1
        distributions["customer_region"][customer_region] += 1
        distributions["sales_region"][sales_region] += 1
        distributions["product_line"][product["product_line"]] += 1
    return rows, distributions


def generate_rates(start: date, end: date) -> tuple[list[tuple[Any, ...]], dict[tuple[date, str], Decimal]]:
    rows: list[tuple[Any, ...]] = []
    rate_map: dict[tuple[date, str], Decimal] = {}
    for rate_date in daterange(start, end):
        for currency in ("CNY", "USD", "EUR"):
            value = exchange_rate(rate_date, currency)
            rows.append((rate_date, currency, value))
            rate_map[(rate_date, currency)] = value
    return rows, rate_map


def generate_expenses(rng: random.Random, start: date, end: date) -> list[tuple[Any, ...]]:
    departments = ["销售部", "研发部", "财务部", "管理部", "市场部", "供应链部"]
    department_base = {
        "销售部": (380_000, 520_000, 240_000, 85_000),
        "研发部": (900_000, 130_000, 180_000, 65_000),
        "财务部": (120_000, 90_000, 210_000, 82_000),
        "管理部": (150_000, 100_000, 260_000, 75_000),
        "市场部": (180_000, 300_000, 190_000, 70_000),
        "供应链部": (220_000, 160_000, 170_000, 60_000),
    }
    rows: list[tuple[Any, ...]] = []
    expense_id = 1
    current = month_start(start)
    while current <= end:
        year_factor = {2024: Decimal("1.00"), 2025: Decimal("1.10"), 2026: Decimal("1.22")}[current.year]
        quarter = (current.month - 1) // 3 + 1
        for department in departments:
            rd_base, selling_base, admin_base, finance_base = department_base[department]
            noise = Decimal(str(rng.uniform(0.94, 1.06)))
            rd_factor = year_factor
            selling_factor = year_factor
            if current.year == 2026 and quarter == 2:
                # 场景 E：2026 Q2 研发投入异常增加。
                rd_factor *= Decimal("1.45")
            if current.year == 2026 and quarter == 3:
                # 场景 E：2026 Q3 销售费用异常增加。
                selling_factor *= Decimal("1.35")
            rd_expense = q2(Decimal(rd_base) * rd_factor * noise)
            selling_expense = q2(Decimal(selling_base) * selling_factor * noise)
            admin_expense = q2(Decimal(admin_base) * year_factor * noise)
            finance_expense = q2(Decimal(finance_base) * year_factor * noise)
            marketing_expense = q2(selling_expense * Decimal("0.28"))
            logistics_expense = q2(selling_expense * Decimal("0.17"))
            warranty_expense = q2(selling_expense * Decimal("0.10"))
            rows.append((
                expense_id,
                current.replace(day=calendar.monthrange(current.year, current.month)[1]),
                department,
                rd_expense,
                selling_expense,
                admin_expense,
                finance_expense,
                marketing_expense,
                logistics_expense,
                warranty_expense,
            ))
            expense_id += 1
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return rows


def assert_course_structure(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema='public' AND table_type='BASE TABLE'
            ORDER BY table_name
        """)
        tables = {row[0] for row in cur.fetchall()}
        if tables != EXPECTED_TABLES:
            raise RuntimeError(f"目标数据库结构不符合课程 5 表基线：{sorted(tables)}")
        for table, expected_columns in EXPECTED_COLUMNS.items():
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name=%s
                ORDER BY ordinal_position
            """, (table,))
            actual = [row[0] for row in cur.fetchall()]
            if actual != expected_columns:
                raise RuntimeError(f"{table} 字段已变化，拒绝进入大数据模式：{actual}")
        cur.execute("""
            SELECT COUNT(*) FROM pg_constraint
            WHERE connamespace='public'::regnamespace AND contype='f'
        """)
        if cur.fetchone()[0] != 2:
            raise RuntimeError("课程基线外键数量不是 2，拒绝写入")


def copy_rows(cur: Any, table: str, columns: list[str], rows: Iterable[tuple[Any, ...]]) -> None:
    column_sql = ", ".join(columns)
    with cur.copy(f"COPY public.{table} ({column_sql}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)


def run_quality_checks(cur: Any, start: date, end: date) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    for table in ("dim_customers", "dim_products", "sales_orders", "exchange_rates", "finance_expenses"):
        cur.execute(f"SELECT COUNT(*) FROM public.{table}")
        checks[f"{table}_count"] = int(cur.fetchone()[0])
    queries = {
        "customer_orphans": """
            SELECT COUNT(*) FROM public.sales_orders o
            LEFT JOIN public.dim_customers c ON c.customer_id=o.customer_id
            WHERE c.customer_id IS NULL
        """,
        "product_orphans": """
            SELECT COUNT(*) FROM public.sales_orders o
            LEFT JOIN public.dim_products p ON p.product_id=o.product_id
            WHERE p.product_id IS NULL
        """,
        "duplicate_order_no_groups": """
            SELECT COUNT(*) FROM (
                SELECT order_no FROM public.sales_orders
                GROUP BY order_no HAVING COUNT(*) > 1
            ) d
        """,
        "missing_order_rates": """
            SELECT COUNT(*) FROM public.sales_orders o
            LEFT JOIN public.exchange_rates er
              ON er.rate_date=o.order_date AND er.currency=o.currency
            WHERE er.currency IS NULL
        """,
        "cny_rate_errors": """
            SELECT COUNT(*) FROM public.exchange_rates
            WHERE currency='CNY' AND rate_to_cny <> 1
        """,
        "invalid_quantity": "SELECT COUNT(*) FROM public.sales_orders WHERE quantity <= 0",
        "invalid_unit_price": "SELECT COUNT(*) FROM public.sales_orders WHERE unit_price <= 0",
        "negative_discount": "SELECT COUNT(*) FROM public.sales_orders WHERE discount_amount < 0",
        "invalid_net_amount": "SELECT COUNT(*) FROM public.sales_orders WHERE net_amount <= 0",
        "gross_less_than_net": "SELECT COUNT(*) FROM public.sales_orders WHERE gross_amount < net_amount",
        "invalid_order_dates": """
            SELECT COUNT(*) FROM public.sales_orders
            WHERE order_date < %s OR order_date > %s
        """,
        "selling_expense_subitem_overflow": """
            SELECT COUNT(*) FROM public.finance_expenses
            WHERE selling_expense < marketing_expense + logistics_expense + warranty_expense
        """,
    }
    for name, query in queries.items():
        if name == "invalid_order_dates":
            cur.execute(query, (start, end))
        else:
            cur.execute(query)
        checks[name] = int(cur.fetchone()[0])
    return checks


def run_distribution_queries(cur: Any) -> dict[str, list[tuple[Any, ...]]]:
    queries = {
        "status_distribution": """
            SELECT order_status, COUNT(*) FROM public.sales_orders
            GROUP BY order_status ORDER BY order_status
        """,
        "currency_distribution": """
            SELECT currency, COUNT(*) FROM public.sales_orders
            GROUP BY currency ORDER BY currency
        """,
        "customer_region_distribution": """
            SELECT region, COUNT(*) FROM public.dim_customers
            GROUP BY region ORDER BY region
        """,
        "sales_region_distribution": """
            SELECT region, COUNT(*) FROM public.sales_orders
            GROUP BY region ORDER BY region
        """,
        "customer_type_distribution": """
            SELECT customer_type, COUNT(*) FROM public.dim_customers
            GROUP BY customer_type ORDER BY customer_type
        """,
        "product_line_distribution": """
            SELECT product_line, COUNT(*) FROM public.dim_products
            GROUP BY product_line ORDER BY product_line
        """,
        "tech_route_distribution": """
            SELECT tech_route, COUNT(*) FROM public.dim_products
            GROUP BY tech_route ORDER BY tech_route
        """,
    }
    result: dict[str, list[tuple[Any, ...]]] = {}
    for name, query in queries.items():
        cur.execute(query)
        result[name] = cur.fetchall()
    return result


def run_business_scenario_queries(cur: Any) -> dict[str, list[tuple[Any, ...]]]:
    queries = {
        "annual_completed_revenue": """
            SELECT EXTRACT(YEAR FROM order_date)::INT AS year,
                   ROUND(SUM(o.net_amount * er.rate_to_cny), 2) AS revenue_rmb
            FROM public.sales_orders o
            JOIN public.exchange_rates er
              ON er.rate_date=o.order_date AND er.currency=o.currency
            WHERE o.order_status='completed'
            GROUP BY year ORDER BY year
        """,
        "quarterly_completed_revenue": """
            SELECT EXTRACT(YEAR FROM order_date)::INT AS year,
                   EXTRACT(QUARTER FROM order_date)::INT AS quarter,
                   ROUND(SUM(o.net_amount * er.rate_to_cny), 2) AS revenue_rmb
            FROM public.sales_orders o
            JOIN public.exchange_rates er
              ON er.rate_date=o.order_date AND er.currency=o.currency
            WHERE o.order_status='completed'
            GROUP BY year, quarter ORDER BY year, quarter
        """,
        "commercial_vehicle_2026_q2_vs_2025_q2": """
            SELECT EXTRACT(YEAR FROM o.order_date)::INT AS year,
                   EXTRACT(QUARTER FROM o.order_date)::INT AS quarter,
                   ROUND(SUM(o.net_amount * er.rate_to_cny), 2) AS revenue_rmb
            FROM public.sales_orders o
            JOIN public.dim_products p ON p.product_id=o.product_id
            JOIN public.exchange_rates er
              ON er.rate_date=o.order_date AND er.currency=o.currency
            WHERE o.order_status='completed'
              AND p.product_line='动力电池-商用车'
              AND ((o.order_date >= DATE '2025-04-01' AND o.order_date < DATE '2025-07-01')
                OR (o.order_date >= DATE '2026-04-01' AND o.order_date < DATE '2026-07-01'))
            GROUP BY year, quarter ORDER BY year, quarter
        """,
        "overall_margin_by_period": """
            SELECT EXTRACT(YEAR FROM o.order_date)::INT AS year,
                   EXTRACT(QUARTER FROM o.order_date)::INT AS quarter,
                   ROUND(
                       SUM(o.net_amount - (p.material_cost + p.labor_cost) * o.quantity)
                       / NULLIF(SUM(o.net_amount), 0), 4
                   ) AS gross_margin_rate
            FROM public.sales_orders o
            JOIN public.dim_products p ON p.product_id=o.product_id
            WHERE o.order_status='completed'
            GROUP BY year, quarter ORDER BY year, quarter
        """,
        "line_margin_by_period": """
            SELECT EXTRACT(YEAR FROM o.order_date)::INT AS year,
                   EXTRACT(QUARTER FROM o.order_date)::INT AS quarter,
                   p.product_line,
                   ROUND(
                       SUM(o.net_amount - (p.material_cost + p.labor_cost) * o.quantity)
                       / NULLIF(SUM(o.net_amount), 0), 4
                   ) AS gross_margin_rate
            FROM public.sales_orders o
            JOIN public.dim_products p ON p.product_id=o.product_id
            WHERE o.order_status='completed'
            GROUP BY year, quarter, p.product_line
            ORDER BY year, quarter, p.product_line
        """,
        "regional_annual_completed_revenue": """
            SELECT c.region, EXTRACT(YEAR FROM o.order_date)::INT AS year,
                   ROUND(SUM(o.net_amount * er.rate_to_cny), 2) AS revenue_rmb
            FROM public.sales_orders o
            JOIN public.dim_customers c ON c.customer_id=o.customer_id
            JOIN public.exchange_rates er
              ON er.rate_date=o.order_date AND er.currency=o.currency
            WHERE o.order_status='completed'
            GROUP BY c.region, year ORDER BY c.region, year
        """,
        "quarterly_expense_anomalies": """
            SELECT EXTRACT(YEAR FROM expense_date)::INT AS year,
                   EXTRACT(QUARTER FROM expense_date)::INT AS quarter,
                   ROUND(SUM(rd_expense), 2) AS rd_expense,
                   ROUND(SUM(selling_expense), 2) AS selling_expense
            FROM public.finance_expenses
            GROUP BY year, quarter ORDER BY year, quarter
        """,
        "customer_region_vs_sales_region": """
            SELECT COUNT(*) FILTER (WHERE c.region=o.region) AS same_region_orders,
                   COUNT(*) FILTER (WHERE c.region<>o.region) AS cross_region_orders,
                   COUNT(*) AS total_orders
            FROM public.sales_orders o
            JOIN public.dim_customers c ON c.customer_id=o.customer_id
        """,
    }
    result: dict[str, list[tuple[Any, ...]]] = {}
    for name, query in queries.items():
        cur.execute(query)
        result[name] = cur.fetchall()
    return result


def validate_business_scenarios(scenarios: dict[str, list[tuple[Any, ...]]]) -> list[str]:
    """把人为注入的趋势转成可重复的验收门槛。"""

    failures: list[str] = []
    annual = {int(year): Decimal(str(revenue)) for year, revenue in scenarios["annual_completed_revenue"]}
    if not (annual[2025] > annual[2024] * Decimal("1.05") and annual[2026] > annual[2025] * Decimal("1.05")):
        failures.append("整体增长：2025、2026 年人民币完成收入没有连续增长")

    commercial = {(int(year), int(quarter)): Decimal(str(revenue)) for year, quarter, revenue in scenarios["commercial_vehicle_2026_q2_vs_2025_q2"]}
    commercial_ratio = commercial[(2026, 2)] / commercial[(2025, 2)]
    if not Decimal("0.70") <= commercial_ratio <= Decimal("0.85"):
        failures.append(f"商用车 2026 Q2 相比 2025 Q2 的收入下降比例不在 15%~30%：ratio={commercial_ratio}")

    margins = {(int(year), int(quarter)): Decimal(str(margin)) for year, quarter, margin in scenarios["overall_margin_by_period"]}
    if not (margins[(2026, 2)] < margins[(2026, 1)] - Decimal("0.0100") or margins[(2026, 3)] < margins[(2026, 1)] - Decimal("0.0100")):
        failures.append("高成本产品组合：2026 Q2/Q3 整体毛利率未较 2026 Q1 明显下降")

    regional = defaultdict(dict)
    for region, year, revenue in scenarios["regional_annual_completed_revenue"]:
        regional[region][int(year)] = Decimal(str(revenue))
    asia_growth = regional["亚太"][2026] / regional["亚太"][2024]
    europe_growth = regional["欧洲"][2026] / regional["欧洲"][2024]
    if not asia_growth > europe_growth * Decimal("1.08"):
        failures.append(f"区域增长差异：亚太增长未明显高于欧洲，asia={asia_growth}, europe={europe_growth}")

    expenses = {(int(year), int(quarter)): (Decimal(str(rd)), Decimal(str(selling))) for year, quarter, rd, selling in scenarios["quarterly_expense_anomalies"]}
    if not expenses[(2026, 2)][0] > expenses[(2026, 1)][0] * Decimal("1.20"):
        failures.append("费用异常：2026 Q2 研发费用未明显高于 Q1")
    if not expenses[(2026, 3)][1] > expenses[(2026, 2)][1] * Decimal("1.10"):
        failures.append("费用异常：2026 Q3 销售费用未明显高于 Q2")

    same_region, cross_region, total_orders = scenarios["customer_region_vs_sales_region"][0]
    cross_rate = Decimal(str(cross_region)) / Decimal(str(total_orders))
    if not Decimal("0.08") <= cross_rate <= Decimal("0.18"):
        failures.append(f"客户区域与销售区域跨区比例不在 8%~18%：ratio={cross_rate}")
    return failures


def print_report(
    seed: int,
    start: date,
    end: date,
    checks: dict[str, Any],
    distributions: dict[str, list[tuple[Any, ...]]],
    scenarios: dict[str, list[tuple[Any, ...]]],
    scenario_failures: list[str],
) -> None:
    print(f"target_database = {DATABASE_NAME}")
    print("=== Course Baseline 大数据生成结果 ===")
    print(f"seed: {seed}")
    print(f"date_range: {start} ~ {end}")
    print("--- row counts ---")
    for key in ("dim_customers_count", "dim_products_count", "sales_orders_count", "exchange_rates_count", "finance_expenses_count"):
        print(f"{key}: {checks[key]}")
    print("--- data quality checks, expected 0 ---")
    for key in (
        "customer_orphans", "product_orphans", "duplicate_order_no_groups", "missing_order_rates",
        "cny_rate_errors", "invalid_quantity", "invalid_unit_price", "negative_discount",
        "invalid_net_amount", "gross_less_than_net", "invalid_order_dates", "selling_expense_subitem_overflow",
    ):
        print(f"{key}: {checks[key]}")
    print("--- distributions ---")
    for name, rows in distributions.items():
        print(f"{name}: {rows}")
    print("--- business scenarios ---")
    for name, rows in scenarios.items():
        print(f"{name}: {rows}")
    print(f"scenario_validation_failures: {scenario_failures}")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Course Baseline V1 大规模确定性模拟数据")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--customer-count", type=int, default=DEFAULT_CUSTOMER_COUNT)
    parser.add_argument("--product-count", type=int, default=DEFAULT_PRODUCT_COUNT)
    parser.add_argument("--order-count", type=int, default=DEFAULT_ORDER_COUNT)
    parser.add_argument("--start-date", type=date.fromisoformat, default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", type=date.fromisoformat, default=DEFAULT_END_DATE)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--database", default=DATABASE_NAME)
    args = parser.parse_args()

    print(f"target_database = {args.database}")
    if args.database != DATABASE_NAME:
        print("安全停止：大数据生成器只允许操作 chatbi_mvp。", file=sys.stderr)
        return 1
    if args.start_date != DEFAULT_START_DATE or args.end_date != DEFAULT_END_DATE:
        print("安全停止：课程基线大数据日期范围必须是 2024-01-01 到 2026-12-31。", file=sys.stderr)
        return 1

    rng = random.Random(args.seed)
    env = load_env(args.env_file)
    config = connection_config(env, DATABASE_NAME)
    customers_rows, customers = generate_customers(rng, args.customer_count)
    products_rows, products = generate_products(rng, args.product_count)
    rates_rows, rate_map = generate_rates(args.start_date, args.end_date)
    orders_rows, _order_distributions = generate_orders(
        rng, customers, products, args.order_count, args.start_date, args.end_date, rate_map
    )
    expense_rows = generate_expenses(rng, args.start_date, args.end_date)

    try:
        with psycopg.connect(**config) as conn:
            assert_course_structure(conn)
            with conn.cursor() as cur:
                # 只清空课程基线的 5 张表；不 DROP，不改结构。
                cur.execute(
                    """
                    TRUNCATE TABLE
                        public.sales_orders,
                        public.exchange_rates,
                        public.finance_expenses,
                        public.dim_products,
                        public.dim_customers
                    """
                )
                copy_rows(cur, "dim_customers", EXPECTED_COLUMNS["dim_customers"], customers_rows)
                copy_rows(cur, "dim_products", EXPECTED_COLUMNS["dim_products"], products_rows)
                copy_rows(cur, "exchange_rates", EXPECTED_COLUMNS["exchange_rates"], rates_rows)
                copy_rows(cur, "sales_orders", EXPECTED_COLUMNS["sales_orders"], orders_rows)
                copy_rows(cur, "finance_expenses", EXPECTED_COLUMNS["finance_expenses"], expense_rows)
                checks = run_quality_checks(cur, args.start_date, args.end_date)
                distributions = run_distribution_queries(cur)
                scenarios = run_business_scenario_queries(cur)
                scenario_failures = validate_business_scenarios(scenarios)
                print_report(args.seed, args.start_date, args.end_date, checks, distributions, scenarios, scenario_failures)
                quality_keys = (
                    "customer_orphans", "product_orphans", "duplicate_order_no_groups", "missing_order_rates",
                    "cny_rate_errors", "invalid_quantity", "invalid_unit_price", "negative_discount",
                    "invalid_net_amount", "gross_less_than_net", "invalid_order_dates", "selling_expense_subitem_overflow",
                )
                failures = [key for key in quality_keys if checks[key] != 0]
                if failures or scenario_failures:
                    raise RuntimeError(f"大数据质量检查失败：quality={failures}, scenarios={scenario_failures}")
                conn.commit()
        return 0
    except (OSError, ValueError, psycopg.Error, RuntimeError) as exc:
        print(f"大数据生成失败，事务已回滚：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
