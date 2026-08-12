"""生成、加载并验证 Sales Mart V1 Demo Data（销售数据集市演示数据）。

代码地图（AI 代码七步掌控法）：
1. 配置与常量：定义固定日期、规模、状态和业务基准；
2. 数据结构：使用不可变行对象表达维度、汇率和销售明细；
3. 工具函数：日期、金额、时间戳和确定性随机数；
4. 生成函数：按业务规则生成维度、SCD2、汇率和订单明细；
5. 加载函数：在一个 PostgreSQL Transaction（事务）中按外键顺序重置/写入；
6. 验证函数：结构关系、SCD2、事实冻结、指标和趋势校验；
7. main：解析参数、运行生成加载验证并输出可复核报告。

边界：
- 只操作 mart_sales；不删除、迁移或更新 public 旧教程基线；
- 不修改 DOMAIN_SPEC、ANALYTICAL_MODEL、Semantic JSON 或 Qdrant；
- 不引入 ETL Framework（数据工程框架），本文件是本地可重复 Demo Data 入口；
- 业务行在成功 Seed（种子装载）后保留，验证失败则整个事务回滚。
"""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, Sequence

import psycopg


ROOT = Path(__file__).resolve().parents[1]
DDL_PATH = ROOT / "database" / "sales_mart" / "001_create_schema.sql"
SCHEMA = "mart_sales"
DATABASE_NAME = "chatbi_mvp"
SOURCE_SYSTEM = "sales_mart_demo_seed"

DEFAULT_SEED = 42
DEFAULT_CUSTOMER_COUNT = 200
DEFAULT_PRODUCT_COUNT = 80
DEFAULT_ORDER_COUNT = 5_000
START_DATE = date(2024, 1, 1)
END_DATE = date(2025, 12, 31)
ANALYSIS_DATE = date(2025, 12, 31)

STATUSES = ("completed", "confirmed", "pending", "cancelled")
STATUS_WEIGHTS = (0.75, 0.10, 0.08, 0.07)
CURRENCIES = ("CNY", "USD", "EUR", "JPY")
CURRENCY_WEIGHTS = (0.68, 0.15, 0.10, 0.07)

MONEY_QUANTUM = Decimal("0.000001")
RATE_QUANTUM = Decimal("0.00000001")
TIMESTAMP = datetime(2026, 1, 1, tzinfo=timezone.utc)

REGIONS = (
    ("EAST", "华东"),
    ("SOUTH", "华南"),
    ("NORTH", "华北"),
    ("CENTRAL", "华中"),
    ("SOUTHWEST", "西南"),
    ("NORTHWEST", "西北"),
)
CUSTOMER_REGIONS = ("华东", "华南", "华北", "华中", "西南", "西北", "东北")
COUNTRIES = ("中国", "日本", "德国", "美国", "新加坡")
CUSTOMER_TYPES = ("Enterprise", "SMB", "Distributor")
INDUSTRIES = ("制造业", "汽车", "电子", "能源", "零售", "物流")
PRODUCT_LINES = ("动力电池", "储能系统", "工业电源", "智能制造")
PRODUCT_CATEGORIES = ("高能量密度", "快充型", "储能型", "工业型", "智能设备")
TECHNOLOGY_ROUTES = ("磷酸铁锂", "三元锂", "钠离子", "固态电池", "高端芯片")

BASE_FX = {
    "CNY": Decimal("1.00000000"),
    "USD": Decimal("7.18000000"),
    "EUR": Decimal("7.82000000"),
    "JPY": Decimal("0.04900000"),
}
FX_TREND = {
    "CNY": Decimal("0"),
    "USD": Decimal("0.01500000"),
    "EUR": Decimal("-0.01000000"),
    "JPY": Decimal("0.00010000"),
}


@dataclass(frozen=True)
class CustomerProfile:
    customer_id: int
    customer_name: str
    customer_type: str
    industry: str
    country: str
    customer_region: str


@dataclass(frozen=True)
class ProductProfile:
    product_id: int
    product_name: str
    product_line: str
    product_category: str
    technology_route: str
    cost_ratio: Decimal


@dataclass(frozen=True)
class DimensionVersion:
    business_id: int
    valid_from: datetime
    valid_to: datetime | None
    is_current: bool
    attributes: tuple[str, ...]


@dataclass(frozen=True)
class GeneratedData:
    dates: list[tuple[Any, ...]]
    currencies: list[tuple[Any, ...]]
    regions: list[tuple[Any, ...]]
    customers: list[tuple[Any, ...]]
    products: list[tuple[Any, ...]]
    rates: list[tuple[Any, ...]]
    sales_lines: list[tuple[Any, ...]]
    customer_versions: dict[int, list[DimensionVersion]]
    product_versions: dict[int, list[DimensionVersion]]


@dataclass(frozen=True)
class SeedReport:
    row_counts: dict[str, int]
    distinct_order_count: int
    distinct_customer_count: int
    distinct_product_count: int
    status_counts: dict[str, int]
    currency_counts: dict[str, int]
    metrics: dict[str, Decimal | None]
    annual_revenue: dict[int, Decimal]
    region_revenue: list[tuple[str, Decimal]]
    product_line_revenue: list[tuple[str, Decimal]]
    customer_region_revenue: list[tuple[str, Decimal]]
    order_1_to_n_orders: int
    customer_history_count: int
    product_history_count: int
    public_table_count: int


def q_money(value: Decimal | int | float) -> Decimal:
    """统一金额精度，避免浮点结果进入 NUMERIC（精确数值）字段。"""

    return Decimal(str(value)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def q_rate(value: Decimal | int | float) -> Decimal:
    return Decimal(str(value)).quantize(RATE_QUANTUM, rounding=ROUND_HALF_UP)


def parse_env(path: Path) -> dict[str, str]:
    """加载本地配置但不输出密码等 Secret（敏感信息）。"""

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
    required = ("POSTGRES_MIGRATOR_USER", "POSTGRES_MIGRATOR_PASSWORD")
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise ValueError(f".env 缺少必要配置：{', '.join(missing)}")
    return {
        "host": env.get("POSTGRES_HOST", "127.0.0.1"),
        "port": int(env.get("POSTGRES_PORT", "5432")),
        "dbname": env.get("POSTGRES_DB", DATABASE_NAME),
        "user": env["POSTGRES_MIGRATOR_USER"],
        "password": env["POSTGRES_MIGRATOR_PASSWORD"],
        "connect_timeout": 10,
    }


def date_range(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def date_key(value: date) -> int:
    return value.year * 10000 + value.month * 100 + value.day


def as_timestamp(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def weighted_choice(rng: random.Random, values: Sequence[Any], weights: Sequence[float]) -> Any:
    return rng.choices(values, weights=weights, k=1)[0]


def generate_dates(start: date, end: date) -> list[tuple[Any, ...]]:
    return [
        (date_key(day), day, day.year, (day.month - 1) // 3 + 1, day.month, day.day)
        for day in date_range(start, end)
    ]


def generate_currencies() -> list[tuple[Any, ...]]:
    names = {"CNY": "人民币", "USD": "美元", "EUR": "欧元", "JPY": "日元"}
    return [
        (index, code, names[code], code == "CNY")
        for index, code in enumerate(CURRENCIES, start=1)
    ]


def generate_regions() -> list[tuple[Any, ...]]:
    return [(index, code, name) for index, (code, name) in enumerate(REGIONS, start=1)]


def generate_customer_profiles(count: int, rng: random.Random) -> list[CustomerProfile]:
    profiles: list[CustomerProfile] = []
    for customer_id in range(1, count + 1):
        customer_type = weighted_choice(rng, CUSTOMER_TYPES, (0.55, 0.30, 0.15))
        industry = weighted_choice(rng, INDUSTRIES, (0.22, 0.20, 0.18, 0.16, 0.14, 0.10))
        country = weighted_choice(rng, COUNTRIES, (0.68, 0.08, 0.08, 0.10, 0.06))
        customer_region = weighted_choice(
            rng,
            CUSTOMER_REGIONS,
            (0.26, 0.18, 0.16, 0.13, 0.10, 0.09, 0.08),
        )
        profiles.append(
            CustomerProfile(
                customer_id=customer_id,
                customer_name=f"客户{customer_id:04d}",
                customer_type=customer_type,
                industry=industry,
                country=country,
                customer_region=customer_region,
            )
        )
    return profiles


def generate_product_profiles(count: int, rng: random.Random) -> list[ProductProfile]:
    profiles: list[ProductProfile] = []
    category_ratios = {
        "高能量密度": Decimal("0.68"),
        "快充型": Decimal("0.62"),
        "储能型": Decimal("0.79"),
        "工业型": Decimal("0.57"),
        "智能设备": Decimal("0.83"),
    }
    for product_id in range(1, count + 1):
        category = weighted_choice(
            rng,
            PRODUCT_CATEGORIES,
            (0.23, 0.19, 0.25, 0.17, 0.16),
        )
        product_line = weighted_choice(rng, PRODUCT_LINES, (0.32, 0.29, 0.21, 0.18))
        technology_route = weighted_choice(rng, TECHNOLOGY_ROUTES, (0.31, 0.23, 0.14, 0.14, 0.18))
        profiles.append(
            ProductProfile(
                product_id=product_id,
                product_name=f"{product_line}-{category}-{product_id:03d}",
                product_line=product_line,
                product_category=category,
                technology_route=technology_route,
                cost_ratio=category_ratios[category],
            )
        )
    return profiles


def build_scd_versions(
    profiles: Sequence[CustomerProfile | ProductProfile],
    rng: random.Random,
    kind: str,
) -> tuple[list[tuple[Any, ...]], dict[int, list[DimensionVersion]]]:
    """生成稳定的两版本 SCD2；历史版本和当前版本均保留。"""

    rows: list[tuple[Any, ...]] = []
    versions: dict[int, list[DimensionVersion]] = {}
    change_count = max(1, round(len(profiles) * 0.12))
    changed_ids = set(rng.sample([profile.customer_id if kind == "customer" else profile.product_id for profile in profiles], change_count))

    for profile in profiles:
        business_id = profile.customer_id if kind == "customer" else profile.product_id
        base_attributes = (
            (profile.customer_name, profile.customer_type, profile.industry, profile.country, profile.customer_region)
            if kind == "customer"
            else (profile.product_name, profile.product_line, profile.product_category, profile.technology_route)
        )
        if business_id not in changed_ids:
            current = DimensionVersion(business_id, as_timestamp(START_DATE), None, True, base_attributes)
            versions[business_id] = [current]
            rows.append(_dimension_row(kind, profile, current, current_attributes=base_attributes))
            continue

        change_day = date(2025, 3, 1) + timedelta(days=(business_id * 17) % 275)
        historical_attributes = _changed_attributes(kind, base_attributes, business_id)
        old = DimensionVersion(
            business_id,
            as_timestamp(START_DATE),
            as_timestamp(change_day),
            False,
            historical_attributes,
        )
        current = DimensionVersion(business_id, as_timestamp(change_day), None, True, base_attributes)
        versions[business_id] = [old, current]
        rows.append(_dimension_row(kind, profile, old, current_attributes=historical_attributes))
        rows.append(_dimension_row(kind, profile, current, current_attributes=base_attributes))
    return rows, versions


def _changed_attributes(kind: str, attributes: tuple[str, ...], business_id: int) -> tuple[str, ...]:
    values = list(attributes)
    if kind == "customer":
        slot = business_id % 3
        if slot == 0:
            index, choices = 1, CUSTOMER_TYPES
        elif slot == 1:
            index, choices = 2, INDUSTRIES
        else:
            index, choices = 4, CUSTOMER_REGIONS
    else:
        slot = business_id % 3
        if slot == 0:
            index, choices = 1, PRODUCT_LINES
        elif slot == 1:
            index, choices = 2, PRODUCT_CATEGORIES
        else:
            index, choices = 3, TECHNOLOGY_ROUTES
    current_value = values[index]
    current_position = choices.index(current_value)
    values[index] = choices[(current_position + 1 + business_id) % len(choices)]
    if values[index] == current_value:
        values[index] = choices[(current_position + 1) % len(choices)]
    return tuple(values)


def _dimension_row(
    kind: str,
    profile: CustomerProfile | ProductProfile,
    version: DimensionVersion,
    current_attributes: tuple[str, ...],
) -> tuple[Any, ...]:
    """按既有 DDL 字段顺序构造一条维度版本。"""

    surrogate_key = (10_000 if kind == "customer" else 20_000) + version.business_id * 10 + (1 if version.is_current else 0)
    if kind == "customer":
        customer_name, customer_type, industry, country, customer_region = current_attributes
        return (
            surrogate_key,
            profile.customer_id,
            customer_name,
            customer_type,
            industry,
            country,
            customer_region,
            version.valid_from,
            version.valid_to,
            version.is_current,
            SOURCE_SYSTEM,
            TIMESTAMP,
        )
    product_name, product_line, product_category, technology_route = current_attributes
    return (
        surrogate_key,
        profile.product_id,
        product_name,
        product_line,
        product_category,
        technology_route,
        version.valid_from,
        version.valid_to,
        version.is_current,
        SOURCE_SYSTEM,
        TIMESTAMP,
    )


def generate_rates(start: date, end: date) -> tuple[list[tuple[Any, ...]], dict[tuple[date, str], Decimal]]:
    rows: list[tuple[Any, ...]] = []
    rate_map: dict[tuple[date, str], Decimal] = {}
    currencies = {code: index for index, code in enumerate(CURRENCIES, start=1)}
    for day_index, current in enumerate(date_range(start, end)):
        year_progress = Decimal(day_index) / Decimal(max(1, (end - start).days))
        seasonal = Decimal(str(((current.month - 1) % 6) - 2.5)) / Decimal("1000")
        for code in CURRENCIES:
            if code == "CNY":
                rate = Decimal("1.00000000")
            else:
                deterministic_wave = Decimal(str(((day_index * 17 + currencies[code] * 11) % 23) - 11)) / Decimal("10000")
                rate = BASE_FX[code] + FX_TREND[code] * year_progress + seasonal + deterministic_wave
                rate = q_rate(rate)
            rate_map[(current, code)] = rate
            rows.append((date_key(current), currencies[code], rate, SOURCE_SYSTEM, TIMESTAMP))
    return rows, rate_map


def _effective_version(versions: dict[int, list[DimensionVersion]], business_id: int, event_date: date) -> DimensionVersion:
    event_timestamp = as_timestamp(event_date)
    for version in versions[business_id]:
        if version.valid_from <= event_timestamp and (version.valid_to is None or event_timestamp < version.valid_to):
            return version
    raise RuntimeError(f"没有找到业务键 {business_id} 在 {event_date} 的有效 SCD2 版本")


def _surrogate_key(kind: str, business_id: int, version: DimensionVersion) -> int:
    return (10_000 if kind == "customer" else 20_000) + business_id * 10 + (1 if version.is_current else 0)


def generate_sales_lines(
    order_count: int,
    customer_profiles: Sequence[CustomerProfile],
    product_profiles: Sequence[ProductProfile],
    customer_versions: dict[int, list[DimensionVersion]],
    product_versions: dict[int, list[DimensionVersion]],
    rate_map: dict[tuple[date, str], Decimal],
    rng: random.Random,
    start: date,
    end: date,
) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    customer_by_id = {profile.customer_id: profile for profile in customer_profiles}
    product_by_id = {profile.product_id: profile for profile in product_profiles}
    line_id = 1
    for order_id in range(1, order_count + 1):
        order_day_index = rng.randrange((end - start).days + 1)
        order_date = start + timedelta(days=order_day_index)
        line_count = weighted_choice(rng, (1, 2, 3, 4, 5), (0.34, 0.29, 0.20, 0.12, 0.05))
        customer_id = weighted_choice(
            rng,
            [profile.customer_id for profile in customer_profiles],
            [1.0 + (2.5 if profile.customer_id <= 10 else 0.0) for profile in customer_profiles],
        )
        customer = customer_by_id[customer_id]
        product_ids = [weighted_choice(rng, list(product_by_id), [1.0] * len(product_by_id)) for _ in range(line_count)]
        status = weighted_choice(rng, STATUSES, STATUS_WEIGHTS)
        confirmation_date: date | None = None
        completion_date: date | None = None
        if status in {"confirmed", "completed"}:
            confirmation_date = min(end, order_date + timedelta(days=rng.randint(1, 12)))
        if status == "completed":
            completion_date = min(end, confirmation_date + timedelta(days=rng.randint(1, 24))) if confirmation_date else order_date
        if status == "cancelled" and rng.random() < 0.42:
            confirmation_date = min(end, order_date + timedelta(days=rng.randint(1, 8)))

        # 2025 提升整体需求；东北区域在 2025 下半年有确定性降幅。
        growth_factor = Decimal("1.18") if order_date.year == 2025 else Decimal("1.00")
        for line_no, product_id in enumerate(product_ids, start=1):
            product = product_by_id[product_id]
            customer_weight = Decimal("1.55") if customer_id <= 10 else Decimal("1.00")
            region_factor = Decimal("0.68") if customer.customer_region == "东北" and order_date >= date(2025, 7, 1) else Decimal("1.00")
            sales_region_index = (order_id + line_no) % len(REGIONS) + 1
            if sales_region_index == 6 and order_date >= date(2025, 7, 1):
                # 西北销售区域在 2025 H2（下半年）构造确定性回落场景。
                region_factor *= Decimal("0.74")
            quantity = Decimal(rng.randint(2, 180)) * customer_weight * region_factor
            quantity = q_money(quantity / Decimal("10"))
            base_price = Decimal(rng.randint(80, 12_000)) * growth_factor
            unit_price = q_money(base_price)
            gross = q_money(quantity * unit_price)
            discount_rate = Decimal(str(rng.choice([0.00, 0.02, 0.04, 0.06, 0.08, 0.12])))
            discount = q_money(gross * discount_rate)
            net_transaction = q_money(gross - discount)
            currency = weighted_choice(rng, CURRENCIES, CURRENCY_WEIGHTS)
            fx_rate: Decimal | None = None
            net_cny: Decimal | None = None
            frozen_unit_cost: Decimal | None = None
            sales_cost: Decimal | None = None
            if status == "completed":
                assert completion_date is not None
                fx_rate = rate_map[(completion_date, currency)]
                net_cny = q_money(net_transaction * fx_rate)
                ratio = product.cost_ratio
                if product.product_category == "储能型" and completion_date.year == 2025 and completion_date.month in {4, 5, 6}:
                    ratio += Decimal("0.08")
                if line_id % 173 == 0:
                    ratio = Decimal("1.03")
                elif line_id % 97 == 0:
                    ratio = Decimal("0.96")
                sales_cost = q_money(net_cny * ratio)
                frozen_unit_cost = q_money(sales_cost / quantity)

            customer_version = _effective_version(customer_versions, customer_id, completion_date or order_date)
            product_version = _effective_version(product_versions, product_id, completion_date or order_date)
            rows.append(
                (
                    line_id,
                    order_id,
                    f"SO{order_id:06d}",
                    line_id,
                    line_no,
                    _surrogate_key("customer", customer_id, customer_version),
                    _surrogate_key("product", product_id, product_version),
                    sales_region_index,
                    CURRENCIES.index(currency) + 1,
                    date_key(order_date),
                    date_key(confirmation_date) if confirmation_date else None,
                    date_key(completion_date) if completion_date else None,
                    status,
                    quantity,
                    unit_price,
                    discount,
                    gross,
                    net_transaction,
                    fx_rate,
                    net_cny,
                    frozen_unit_cost,
                    sales_cost,
                    SOURCE_SYSTEM,
                    TIMESTAMP,
                )
            )
            line_id += 1
    return rows


def generate_data(
    seed: int = DEFAULT_SEED,
    customer_count: int = DEFAULT_CUSTOMER_COUNT,
    product_count: int = DEFAULT_PRODUCT_COUNT,
    order_count: int = DEFAULT_ORDER_COUNT,
    start: date = START_DATE,
    end: date = END_DATE,
) -> GeneratedData:
    if start != START_DATE or end != END_DATE:
        raise ValueError("Sales Mart Demo Data 日期范围必须是 2024-01-01 到 2025-12-31")
    if customer_count < 1 or product_count < 1 or order_count < 1:
        raise ValueError("客户、产品和订单数量必须为正数")
    rng = random.Random(seed)
    customer_profiles = generate_customer_profiles(customer_count, rng)
    product_profiles = generate_product_profiles(product_count, rng)
    customer_rows, customer_versions = build_scd_versions(customer_profiles, rng, "customer")
    product_rows, product_versions = build_scd_versions(product_profiles, rng, "product")
    rates, rate_map = generate_rates(start, end)
    return GeneratedData(
        dates=generate_dates(start, end),
        currencies=generate_currencies(),
        regions=generate_regions(),
        customers=customer_rows,
        products=product_rows,
        rates=rates,
        sales_lines=generate_sales_lines(
            order_count,
            customer_profiles,
            product_profiles,
            customer_versions,
            product_versions,
            rate_map,
            rng,
            start,
            end,
        ),
        customer_versions=customer_versions,
        product_versions=product_versions,
    )


def copy_rows(cur: Any, table: str, columns: Sequence[str], rows: Iterable[tuple[Any, ...]]) -> None:
    columns_sql = ", ".join(columns)
    with cur.copy(f"COPY {SCHEMA}.{table} ({columns_sql}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)


def apply_ddl(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(DDL_PATH.read_text(encoding="utf-8"))


def reset_mart_sales(cur: Any) -> None:
    """只清理 mart_sales 业务数据，保留 Schema（模式）和索引。"""

    cur.execute(
        f"""
        TRUNCATE TABLE
            {SCHEMA}.fct_sales_order_line,
            {SCHEMA}.fct_exchange_rate_daily,
            {SCHEMA}.dim_product,
            {SCHEMA}.dim_customer,
            {SCHEMA}.dim_sales_region,
            {SCHEMA}.dim_currency,
            {SCHEMA}.dim_date
        RESTART IDENTITY
        """
    )


def load_data(conn: psycopg.Connection[Any], data: GeneratedData, reset: bool) -> None:
    with conn.cursor() as cur:
        if reset:
            reset_mart_sales(cur)
        copy_rows(cur, "dim_date", ("date_key", "full_date", "year", "quarter", "month", "day"), data.dates)
        copy_rows(cur, "dim_currency", ("currency_key", "currency_code", "currency_name", "is_analysis_currency"), data.currencies)
        copy_rows(cur, "dim_sales_region", ("sales_region_key", "sales_region_code", "sales_region_name"), data.regions)
        copy_rows(
            cur,
            "dim_customer",
            ("customer_key", "customer_id", "customer_name", "customer_type", "industry", "country", "customer_region", "valid_from", "valid_to", "is_current", "source_system", "source_updated_at"),
            data.customers,
        )
        copy_rows(
            cur,
            "dim_product",
            ("product_key", "product_id", "product_name", "product_line", "product_category", "technology_route", "valid_from", "valid_to", "is_current", "source_system", "source_updated_at"),
            data.products,
        )
        copy_rows(
            cur,
            "fct_exchange_rate_daily",
            ("rate_date_key", "currency_key", "rate_to_cny", "source_system", "source_updated_at"),
            data.rates,
        )
        copy_rows(
            cur,
            "fct_sales_order_line",
            ("sales_order_line_key", "order_id", "order_no", "order_line_id", "order_line_no", "customer_key", "product_key", "sales_region_key", "transaction_currency_key", "order_date_key", "confirmation_date_key", "completion_date_key", "order_status", "quantity", "unit_price_transaction", "discount_amount_transaction", "gross_sales_amount_transaction", "net_sales_amount_transaction", "fx_rate_to_cny", "net_sales_amount_cny", "frozen_unit_cost_cny", "sales_cost_amount_cny", "source_system", "source_updated_at"),
            data.sales_lines,
        )


def fetch_report(conn: psycopg.Connection[Any]) -> SeedReport:
    with conn.cursor() as cur:
        tables = (
            "dim_date",
            "dim_currency",
            "dim_sales_region",
            "dim_customer",
            "dim_product",
            "fct_exchange_rate_daily",
            "fct_sales_order_line",
        )
        row_counts: dict[str, int] = {}
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.{table}")
            row_counts[table] = int(cur.fetchone()[0])

        cur.execute(f"SELECT order_status, COUNT(*) FROM {SCHEMA}.fct_sales_order_line GROUP BY order_status ORDER BY order_status")
        status_counts = {str(status): int(count) for status, count in cur.fetchall()}
        cur.execute(f"SELECT COUNT(DISTINCT order_id) FROM {SCHEMA}.fct_sales_order_line")
        distinct_order_count = int(cur.fetchone()[0])
        cur.execute(f"SELECT COUNT(DISTINCT customer_id) FROM {SCHEMA}.dim_customer")
        distinct_customer_count = int(cur.fetchone()[0])
        cur.execute(f"SELECT COUNT(DISTINCT product_id) FROM {SCHEMA}.dim_product")
        distinct_product_count = int(cur.fetchone()[0])
        cur.execute(
            f"""
            SELECT c.currency_code, COUNT(*)
            FROM {SCHEMA}.fct_sales_order_line AS line
            JOIN {SCHEMA}.dim_currency AS c ON c.currency_key = line.transaction_currency_key
            GROUP BY c.currency_code ORDER BY c.currency_code
            """
        )
        currency_counts = {str(code): int(count) for code, count in cur.fetchall()}
        cur.execute(
            f"""
            SELECT
                SUM(quantity),
                SUM(net_sales_amount_cny),
                SUM(sales_cost_amount_cny),
                SUM(net_sales_amount_cny) - SUM(sales_cost_amount_cny),
                (SUM(net_sales_amount_cny) - SUM(sales_cost_amount_cny))
                    / NULLIF(SUM(net_sales_amount_cny), 0)
            FROM {SCHEMA}.fct_sales_order_line
            WHERE order_status = 'completed'
            """
        )
        quantity, revenue, cost, gross_profit, margin = cur.fetchone()
        metrics = {
            "sales_quantity": _decimal_or_none(quantity),
            "sales_revenue_cny": _decimal_or_none(revenue),
            "sales_cost_cny": _decimal_or_none(cost),
            "gross_profit_cny": _decimal_or_none(gross_profit),
            "gross_margin": _decimal_or_none(margin),
        }
        cur.execute(
            f"""
            SELECT d.year, ROUND(SUM(line.net_sales_amount_cny), 2)
            FROM {SCHEMA}.fct_sales_order_line AS line
            JOIN {SCHEMA}.dim_date AS d ON d.date_key = line.completion_date_key
            WHERE line.order_status = 'completed'
            GROUP BY d.year ORDER BY d.year
            """
        )
        annual_revenue = {int(year): Decimal(str(value)) for year, value in cur.fetchall()}
        region_revenue = _grouped_revenue(cur, "sales_region", "sales_region_name")
        product_line_revenue = _grouped_revenue(cur, "product", "product_line")
        customer_region_revenue = _grouped_revenue(cur, "customer", "customer_region")
        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM (
                SELECT order_id FROM {SCHEMA}.fct_sales_order_line
                GROUP BY order_id HAVING COUNT(*) > 1
            ) AS multi_line_orders
            """
        )
        order_1_to_n_orders = int(cur.fetchone()[0])
        cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.dim_customer WHERE NOT is_current")
        customer_history_count = int(cur.fetchone()[0])
        cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.dim_product WHERE NOT is_current")
        product_history_count = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")
        public_table_count = int(cur.fetchone()[0])
    return SeedReport(
        row_counts,
        distinct_order_count,
        distinct_customer_count,
        distinct_product_count,
        status_counts,
        currency_counts,
        metrics,
        annual_revenue,
        region_revenue,
        product_line_revenue,
        customer_region_revenue,
        order_1_to_n_orders,
        customer_history_count,
        product_history_count,
        public_table_count,
    )


def _decimal_or_none(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _grouped_revenue(cur: Any, dimension: str, column: str) -> list[tuple[str, Decimal]]:
    joins = {
        "sales_region": f"JOIN {SCHEMA}.dim_sales_region AS dimension ON dimension.sales_region_key = line.sales_region_key",
        "product": f"JOIN {SCHEMA}.dim_product AS dimension ON dimension.product_key = line.product_key",
        "customer": f"JOIN {SCHEMA}.dim_customer AS dimension ON dimension.customer_key = line.customer_key",
    }
    cur.execute(
        f"""
        SELECT dimension.{column}, ROUND(SUM(line.net_sales_amount_cny), 2)
        FROM {SCHEMA}.fct_sales_order_line AS line
        {joins[dimension]}
        WHERE line.order_status = 'completed'
        GROUP BY dimension.{column}
        ORDER BY dimension.{column}
        """
    )
    return [(str(name), Decimal(str(value))) for name, value in cur.fetchall()]


def validate_report(conn: psycopg.Connection[Any], data: GeneratedData, report: SeedReport) -> list[str]:
    failures: list[str] = []
    expected_dates = (END_DATE - START_DATE).days + 1
    expected_rates = expected_dates * len(CURRENCIES)
    if report.row_counts["dim_date"] != expected_dates:
        failures.append(f"dim_date 行数错误：{report.row_counts['dim_date']}")
    if report.row_counts["fct_exchange_rate_daily"] != expected_rates:
        failures.append(f"汇率事实行数错误：{report.row_counts['fct_exchange_rate_daily']}")
    if not 8_000 <= report.row_counts["fct_sales_order_line"] <= 12_000:
        failures.append(f"订单明细行数不在 8,000~12,000：{report.row_counts['fct_sales_order_line']}")
    expected_order_count = len({row[1] for row in data.sales_lines})
    if report.distinct_order_count != expected_order_count:
        failures.append(f"订单数量不一致：report={report.distinct_order_count}, generated={expected_order_count}")
    if report.distinct_customer_count != len(data.customer_versions):
        failures.append(f"客户业务键数量不一致：{report.distinct_customer_count}")
    if report.distinct_product_count != len(data.product_versions):
        failures.append(f"产品业务键数量不一致：{report.distinct_product_count}")
    if report.order_1_to_n_orders < 1:
        failures.append("没有发现一张订单包含多条订单明细")
    if report.customer_history_count < 20 or report.product_history_count < 8:
        failures.append("Customer/Product SCD2 历史版本数量不足")
    if report.public_table_count != 5:
        failures.append(f"public 旧基线表数量变化：{report.public_table_count}")

    with conn.cursor() as cur:
        checks = {
            "duplicate_order_line_id": f"SELECT COUNT(*) FROM (SELECT order_line_id FROM {SCHEMA}.fct_sales_order_line GROUP BY order_line_id HAVING COUNT(*) > 1) d",
            "duplicate_order_line_no": f"SELECT COUNT(*) FROM (SELECT order_id, order_line_no FROM {SCHEMA}.fct_sales_order_line GROUP BY order_id, order_line_no HAVING COUNT(*) > 1) d",
            "completed_missing_completion": f"SELECT COUNT(*) FROM {SCHEMA}.fct_sales_order_line WHERE order_status='completed' AND completion_date_key IS NULL",
            "completed_missing_fx": f"SELECT COUNT(*) FROM {SCHEMA}.fct_sales_order_line WHERE order_status='completed' AND fx_rate_to_cny IS NULL",
            "completed_missing_cny": f"SELECT COUNT(*) FROM {SCHEMA}.fct_sales_order_line WHERE order_status='completed' AND net_sales_amount_cny IS NULL",
            "completed_missing_cost": f"SELECT COUNT(*) FROM {SCHEMA}.fct_sales_order_line WHERE order_status='completed' AND (frozen_unit_cost_cny IS NULL OR sales_cost_amount_cny IS NULL)",
            "invalid_time_order": f"""
                SELECT COUNT(*)
                FROM {SCHEMA}.fct_sales_order_line AS line
                JOIN {SCHEMA}.dim_date AS od ON od.date_key = line.order_date_key
                LEFT JOIN {SCHEMA}.dim_date AS cd ON cd.date_key = line.confirmation_date_key
                LEFT JOIN {SCHEMA}.dim_date AS fd ON fd.date_key = line.completion_date_key
                WHERE (cd.full_date IS NOT NULL AND cd.full_date < od.full_date)
                   OR (fd.full_date IS NOT NULL AND fd.full_date < COALESCE(cd.full_date, od.full_date))
            """,
            "scd_customer_current_duplicates": f"SELECT COUNT(*) FROM (SELECT customer_id FROM {SCHEMA}.dim_customer WHERE is_current GROUP BY customer_id HAVING COUNT(*) > 1) d",
            "scd_product_current_duplicates": f"SELECT COUNT(*) FROM (SELECT product_id FROM {SCHEMA}.dim_product WHERE is_current GROUP BY product_id HAVING COUNT(*) > 1) d",
            "cny_rate_errors": f"""
                SELECT COUNT(*)
                FROM {SCHEMA}.fct_exchange_rate_daily AS rate
                JOIN {SCHEMA}.dim_currency AS currency ON currency.currency_key = rate.currency_key
                WHERE currency.currency_code = 'CNY' AND rate.rate_to_cny <> 1
            """,
            "completed_fx_date_mismatch": f"""
                SELECT COUNT(*)
                FROM {SCHEMA}.fct_sales_order_line AS line
                JOIN {SCHEMA}.dim_date AS completion ON completion.date_key = line.completion_date_key
                JOIN {SCHEMA}.dim_currency AS currency ON currency.currency_key = line.transaction_currency_key
                JOIN {SCHEMA}.fct_exchange_rate_daily AS rate
                  ON rate.rate_date_key = line.completion_date_key
                 AND rate.currency_key = line.transaction_currency_key
                WHERE line.order_status = 'completed'
                  AND line.fx_rate_to_cny <> rate.rate_to_cny
            """,
            "customer_version_mismatch": f"""
                SELECT COUNT(*)
                FROM {SCHEMA}.fct_sales_order_line AS line
                JOIN {SCHEMA}.dim_date AS event_date ON event_date.date_key = COALESCE(line.completion_date_key, line.order_date_key)
                JOIN {SCHEMA}.dim_customer AS customer ON customer.customer_key = line.customer_key
                WHERE event_date.full_date < customer.valid_from::DATE
                   OR (customer.valid_to IS NOT NULL AND event_date.full_date >= customer.valid_to::DATE)
            """,
            "product_version_mismatch": f"""
                SELECT COUNT(*)
                FROM {SCHEMA}.fct_sales_order_line AS line
                JOIN {SCHEMA}.dim_date AS event_date ON event_date.date_key = COALESCE(line.completion_date_key, line.order_date_key)
                JOIN {SCHEMA}.dim_product AS product ON product.product_key = line.product_key
                WHERE event_date.full_date < product.valid_from::DATE
                   OR (product.valid_to IS NOT NULL AND event_date.full_date >= product.valid_to::DATE)
            """,
            "completed_revenue_null": f"SELECT COUNT(*) FROM {SCHEMA}.fct_sales_order_line WHERE order_status='completed' AND (net_sales_amount_cny IS NULL OR sales_cost_amount_cny IS NULL)",
            "non_positive_exchange_rate": f"SELECT COUNT(*) FROM {SCHEMA}.fct_exchange_rate_daily WHERE rate_to_cny <= 0",
            "completed_cny_fx_errors": f"""
                SELECT COUNT(*)
                FROM {SCHEMA}.fct_sales_order_line AS line
                JOIN {SCHEMA}.dim_currency AS currency ON currency.currency_key = line.transaction_currency_key
                WHERE line.order_status = 'completed'
                  AND currency.currency_code = 'CNY'
                  AND line.fx_rate_to_cny <> 1
            """,
        }
        for name, query in checks.items():
            cur.execute(query)
            value = int(cur.fetchone()[0])
            if value != 0:
                failures.append(f"{name}={value}")
    return failures


def report_lines(report: SeedReport) -> list[str]:
    lines = ["=== Sales Mart V1 Demo Data ==="]
    lines.append("--- row counts ---")
    lines.extend(f"{name}: {count}" for name, count in report.row_counts.items())
    lines.append(f"sales_orders_distinct: {report.distinct_order_count}")
    lines.append(f"customers_distinct_business_id: {report.distinct_customer_count}")
    lines.append(f"products_distinct_business_id: {report.distinct_product_count}")
    lines.append(f"order_1_to_n_orders: {report.order_1_to_n_orders}")
    lines.append(f"customer_scd2_history_rows: {report.customer_history_count}")
    lines.append(f"product_scd2_history_rows: {report.product_history_count}")
    lines.append("--- status distribution ---")
    lines.extend(f"{status}: {report.status_counts.get(status, 0)}" for status in STATUSES)
    lines.append("--- currency distribution ---")
    lines.extend(f"{code}: {report.currency_counts.get(code, 0)}" for code in CURRENCIES)
    lines.append("--- metric sanity ---")
    lines.extend(f"{name}: {value}" for name, value in report.metrics.items())
    lines.append("--- annual completed revenue (CNY) ---")
    lines.extend(f"{year}: {value}" for year, value in report.annual_revenue.items())
    lines.append("--- completed revenue by sales region (CNY) ---")
    lines.extend(f"{name}: {value}" for name, value in report.region_revenue)
    lines.append("--- completed revenue by product line (CNY) ---")
    lines.extend(f"{name}: {value}" for name, value in report.product_line_revenue)
    lines.append("--- completed revenue by customer region (CNY) ---")
    lines.extend(f"{name}: {value}" for name, value in report.customer_region_revenue)
    lines.append(f"public_table_count: {report.public_table_count}")
    return lines
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成并加载 Sales Mart V1 可重复 Demo Data")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--customer-count", type=int, default=DEFAULT_CUSTOMER_COUNT)
    parser.add_argument("--product-count", type=int, default=DEFAULT_PRODUCT_COUNT)
    parser.add_argument("--order-count", type=int, default=DEFAULT_ORDER_COUNT)
    parser.add_argument("--start-date", type=date.fromisoformat, default=START_DATE)
    parser.add_argument("--end-date", type=date.fromisoformat, default=END_DATE)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--database", default=DATABASE_NAME)
    parser.add_argument("--reset", action="store_true", help="先清空 mart_sales 业务数据再重新加载")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.database != DATABASE_NAME:
        print(f"安全停止：Demo Data 只允许操作 {DATABASE_NAME}，收到 {args.database!r}", file=sys.stderr)
        return 1
    if args.start_date != START_DATE or args.end_date != END_DATE:
        print("安全停止：Demo Data 日期范围必须是 2024-01-01 到 2025-12-31", file=sys.stderr)
        return 1
    try:
        data = generate_data(args.seed, args.customer_count, args.product_count, args.order_count, args.start_date, args.end_date)
        env = parse_env(args.env_file)
        with psycopg.connect(**connection_config(env)) as conn:
            conn.autocommit = False
            with conn.cursor() as cur:
                cur.execute("SELECT current_database()")
                actual_database = str(cur.fetchone()[0])
            if actual_database != DATABASE_NAME:
                raise RuntimeError(
                    f"安全停止：实际连接数据库为 {actual_database!r}，目标必须是 {DATABASE_NAME!r}"
                )
            apply_ddl(conn)
            load_data(conn, data, reset=args.reset)
            report = fetch_report(conn)
            failures = validate_report(conn, data, report)
            print(f"seed: {args.seed}")
            print(f"date_range: {args.start_date} ~ {args.end_date}")
            print("\n".join(report_lines(report)))
            if failures:
                raise RuntimeError("Demo Data 验证失败：" + "; ".join(failures))
            conn.commit()
        print("validation_result: PASS")
        return 0
    except (OSError, ValueError, psycopg.Error, RuntimeError) as exc:
        print(f"Demo Data 生成/加载失败，事务已回滚：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
