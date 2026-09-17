-- CI-only PostgreSQL fixture（仅用于 GitHub Actions 集成测试）。
-- 不包含真实业务数据，也不用于本地开发数据库初始化。

\set ON_ERROR_STOP on

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'chatbi_app'
    ) THEN
        CREATE ROLE chatbi_app LOGIN;
    END IF;
END
$$;

ALTER ROLE chatbi_app WITH LOGIN PASSWORD 'ci-app-password';

\ir ../sales_mart/001_create_schema.sql

INSERT INTO mart_sales.dim_date (
    date_key,
    full_date,
    year,
    quarter,
    month,
    day
)
SELECT
    to_char(day_value::date, 'YYYYMMDD')::INTEGER,
    day_value::date,
    EXTRACT(YEAR FROM day_value)::SMALLINT,
    EXTRACT(QUARTER FROM day_value)::SMALLINT,
    EXTRACT(MONTH FROM day_value)::SMALLINT,
    EXTRACT(DAY FROM day_value)::SMALLINT
FROM generate_series(
    DATE '2025-01-01',
    DATE '2025-01-31',
    INTERVAL '1 day'
) AS dates(day_value);

INSERT INTO mart_sales.dim_customer (
    customer_id,
    customer_name,
    customer_type,
    industry,
    country,
    customer_region,
    valid_from,
    valid_to,
    is_current,
    source_system,
    source_updated_at
)
VALUES
    (
        1001,
        'CI Customer 1',
        'enterprise',
        'technology',
        'China',
        'East',
        TIMESTAMPTZ '2025-01-01 00:00:00+00',
        NULL,
        TRUE,
        'ci_fixture',
        TIMESTAMPTZ '2025-01-01 00:00:00+00'
    );

INSERT INTO mart_sales.dim_product (
    product_id,
    product_name,
    product_line,
    product_category,
    technology_route,
    valid_from,
    valid_to,
    is_current,
    source_system,
    source_updated_at
)
VALUES
    (
        2001,
        'CI Product 1',
        'ci-line',
        'ci-category',
        'ci-route',
        TIMESTAMPTZ '2025-01-01 00:00:00+00',
        NULL,
        TRUE,
        'ci_fixture',
        TIMESTAMPTZ '2025-01-01 00:00:00+00'
    );

INSERT INTO mart_sales.dim_sales_region (
    sales_region_code,
    sales_region_name
)
VALUES ('CI-EAST', 'CI East');

INSERT INTO mart_sales.dim_currency (
    currency_code,
    currency_name,
    is_analysis_currency
)
VALUES ('CNY', 'Chinese Yuan', TRUE);

INSERT INTO mart_sales.fct_exchange_rate_daily (
    rate_date_key,
    currency_key,
    rate_to_cny,
    source_system,
    source_updated_at
)
SELECT
    date_key,
    currency_key,
    1.0,
    'ci_fixture',
    TIMESTAMPTZ '2025-01-01 00:00:00+00'
FROM mart_sales.dim_date
CROSS JOIN mart_sales.dim_currency
WHERE currency_code = 'CNY';

WITH fixture_rows AS (
    SELECT
        item_number,
        (DATE '2025-01-01' + ((item_number - 1) % 31))::DATE AS order_date
    FROM generate_series(1, 120) AS items(item_number)
)
INSERT INTO mart_sales.fct_sales_order_line (
    order_id,
    order_no,
    order_line_id,
    order_line_no,
    customer_key,
    product_key,
    sales_region_key,
    transaction_currency_key,
    order_date_key,
    confirmation_date_key,
    completion_date_key,
    order_status,
    quantity,
    unit_price_transaction,
    discount_amount_transaction,
    gross_sales_amount_transaction,
    net_sales_amount_transaction,
    fx_rate_to_cny,
    net_sales_amount_cny,
    frozen_unit_cost_cny,
    sales_cost_amount_cny,
    source_system,
    source_updated_at
)
SELECT
    100000 + fixture.item_number,
    'CI-' || fixture.item_number,
    200000 + fixture.item_number,
    1,
    customer.customer_key,
    product.product_key,
    region.sales_region_key,
    currency.currency_key,
    date_row.date_key,
    date_row.date_key,
    date_row.date_key,
    'completed',
    1,
    100,
    0,
    100,
    100,
    1,
    100,
    60,
    60,
    'ci_fixture',
    TIMESTAMPTZ '2025-01-01 00:00:00+00'
FROM fixture_rows AS fixture
JOIN mart_sales.dim_date AS date_row
    ON date_row.full_date = fixture.order_date
CROSS JOIN mart_sales.dim_customer AS customer
CROSS JOIN mart_sales.dim_product AS product
CROSS JOIN mart_sales.dim_sales_region AS region
CROSS JOIN mart_sales.dim_currency AS currency
WHERE customer.customer_id = 1001
  AND product.product_id = 2001
  AND region.sales_region_code = 'CI-EAST'
  AND currency.currency_code = 'CNY';

\ir ../grants.sql
