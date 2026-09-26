-- Synthetic development data for chatbi_mvp only.
-- Seed version: chatbi-sales-mart-dev-v1
-- Reapplying this version is idempotent. A new version requires a PostgreSQL reset.

CREATE TABLE IF NOT EXISTS mart_sales.dev_seed_metadata (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    seed_version TEXT NOT NULL,
    seeded_at TIMESTAMPTZ NOT NULL
);

DO $$
DECLARE
    current_version TEXT;
BEGIN
    SELECT seed_version
    INTO current_version
    FROM mart_sales.dev_seed_metadata
    WHERE singleton;

    IF current_version IS NOT NULL
       AND current_version <> 'chatbi-sales-mart-dev-v1' THEN
        RAISE EXCEPTION
            'Development seed version differs; reset the local PostgreSQL volume before rebuilding';
    END IF;
END
$$;

INSERT INTO mart_sales.dim_date (
    date_key,
    full_date,
    year,
    quarter,
    month,
    day
)
SELECT
    to_char(day_value::DATE, 'YYYYMMDD')::INTEGER,
    day_value::DATE,
    EXTRACT(YEAR FROM day_value)::SMALLINT,
    EXTRACT(QUARTER FROM day_value)::SMALLINT,
    EXTRACT(MONTH FROM day_value)::SMALLINT,
    EXTRACT(DAY FROM day_value)::SMALLINT
FROM generate_series(
    DATE '2024-01-01',
    DATE '2025-12-31',
    INTERVAL '1 day'
) AS dates(day_value)
ON CONFLICT (date_key) DO UPDATE
SET full_date = EXCLUDED.full_date,
    year = EXCLUDED.year,
    quarter = EXCLUDED.quarter,
    month = EXCLUDED.month,
    day = EXCLUDED.day;

INSERT INTO mart_sales.dim_customer (
    customer_key,
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
    source_updated_at,
    loaded_at
)
VALUES
    (1001, 1001, 'Northstar Components', 'enterprise', 'manufacturing', 'China', 'East', '2023-01-01 00:00:00+00', NULL, TRUE, 'chatbi_dev_seed_v1', '2025-12-31 00:00:00+00', '2025-12-31 00:00:00+00'),
    (1002, 1002, 'Harbor Retail Group', 'enterprise', 'retail', 'China', 'South', '2023-01-01 00:00:00+00', NULL, TRUE, 'chatbi_dev_seed_v1', '2025-12-31 00:00:00+00', '2025-12-31 00:00:00+00'),
    (1003, 1003, 'Pinecone Workshop', 'smb', 'manufacturing', 'China', 'North', '2023-01-01 00:00:00+00', NULL, TRUE, 'chatbi_dev_seed_v1', '2025-12-31 00:00:00+00', '2025-12-31 00:00:00+00'),
    (1004, 1004, 'Riverbend Labs', 'enterprise', 'technology', 'China', 'West', '2023-01-01 00:00:00+00', NULL, TRUE, 'chatbi_dev_seed_v1', '2025-12-31 00:00:00+00', '2025-12-31 00:00:00+00'),
    (1005, 1005, 'Cedar Public Works', 'public', 'public services', 'China', 'East', '2023-01-01 00:00:00+00', NULL, TRUE, 'chatbi_dev_seed_v1', '2025-12-31 00:00:00+00', '2025-12-31 00:00:00+00'),
    (1006, 1006, 'Summit Data Systems', 'smb', 'technology', 'China', 'Central', '2023-01-01 00:00:00+00', NULL, TRUE, 'chatbi_dev_seed_v1', '2025-12-31 00:00:00+00', '2025-12-31 00:00:00+00'),
    (1007, 1007, 'Meadow Supply Co', 'channel', 'distribution', 'China', 'South', '2023-01-01 00:00:00+00', NULL, TRUE, 'chatbi_dev_seed_v1', '2025-12-31 00:00:00+00', '2025-12-31 00:00:00+00'),
    (1008, 1008, 'Lighthouse Energy', 'enterprise', 'energy', 'China', 'Northwest', '2023-01-01 00:00:00+00', NULL, TRUE, 'chatbi_dev_seed_v1', '2025-12-31 00:00:00+00', '2025-12-31 00:00:00+00')
ON CONFLICT ON CONSTRAINT uq_dim_customer_business_version DO UPDATE
SET customer_key = EXCLUDED.customer_key,
    customer_name = EXCLUDED.customer_name,
    customer_type = EXCLUDED.customer_type,
    industry = EXCLUDED.industry,
    country = EXCLUDED.country,
    customer_region = EXCLUDED.customer_region,
    valid_to = EXCLUDED.valid_to,
    is_current = EXCLUDED.is_current,
    source_system = EXCLUDED.source_system,
    source_updated_at = EXCLUDED.source_updated_at,
    loaded_at = EXCLUDED.loaded_at;

INSERT INTO mart_sales.dim_product (
    product_key,
    product_id,
    product_name,
    product_line,
    product_category,
    technology_route,
    valid_from,
    valid_to,
    is_current,
    source_system,
    source_updated_at,
    loaded_at
)
VALUES
    (2001, 2001, 'Aster Controller', 'automation', 'controller', 'edge-control', '2023-01-01 00:00:00+00', NULL, TRUE, 'chatbi_dev_seed_v1', '2025-12-31 00:00:00+00', '2025-12-31 00:00:00+00'),
    (2002, 2002, 'Birch Sensor', 'automation', 'sensor', 'precision-sensing', '2023-01-01 00:00:00+00', NULL, TRUE, 'chatbi_dev_seed_v1', '2025-12-31 00:00:00+00', '2025-12-31 00:00:00+00'),
    (2003, 2003, 'Cobalt Gateway', 'connectivity', 'gateway', 'industrial-network', '2023-01-01 00:00:00+00', NULL, TRUE, 'chatbi_dev_seed_v1', '2025-12-31 00:00:00+00', '2025-12-31 00:00:00+00'),
    (2004, 2004, 'Dawn Analytics Kit', 'software', 'analytics', 'stream-processing', '2023-01-01 00:00:00+00', NULL, TRUE, 'chatbi_dev_seed_v1', '2025-12-31 00:00:00+00', '2025-12-31 00:00:00+00'),
    (2005, 2005, 'Elm Drive Unit', 'automation', 'drive', 'motion-control', '2023-01-01 00:00:00+00', NULL, TRUE, 'chatbi_dev_seed_v1', '2025-12-31 00:00:00+00', '2025-12-31 00:00:00+00'),
    (2006, 2006, 'Fern Cloud Node', 'software', 'cloud', 'distributed-compute', '2023-01-01 00:00:00+00', NULL, TRUE, 'chatbi_dev_seed_v1', '2025-12-31 00:00:00+00', '2025-12-31 00:00:00+00'),
    (2007, 2007, 'Grove Power Module', 'energy', 'power', 'power-conversion', '2023-01-01 00:00:00+00', NULL, TRUE, 'chatbi_dev_seed_v1', '2025-12-31 00:00:00+00', '2025-12-31 00:00:00+00'),
    (2008, 2008, 'Harbor Vision Unit', 'connectivity', 'vision', 'computer-vision', '2023-01-01 00:00:00+00', NULL, TRUE, 'chatbi_dev_seed_v1', '2025-12-31 00:00:00+00', '2025-12-31 00:00:00+00')
ON CONFLICT ON CONSTRAINT uq_dim_product_business_version DO UPDATE
SET product_key = EXCLUDED.product_key,
    product_name = EXCLUDED.product_name,
    product_line = EXCLUDED.product_line,
    product_category = EXCLUDED.product_category,
    technology_route = EXCLUDED.technology_route,
    valid_to = EXCLUDED.valid_to,
    is_current = EXCLUDED.is_current,
    source_system = EXCLUDED.source_system,
    source_updated_at = EXCLUDED.source_updated_at,
    loaded_at = EXCLUDED.loaded_at;

INSERT INTO mart_sales.dim_sales_region (
    sales_region_key,
    sales_region_code,
    sales_region_name
)
VALUES
    (3001, 'DEV-EAST', 'East'),
    (3002, 'DEV-SOUTH', 'South'),
    (3003, 'DEV-NORTH', 'North'),
    (3004, 'DEV-WEST', 'West'),
    (3005, 'DEV-CENTRAL', 'Central'),
    (3006, 'DEV-NORTHWEST', 'Northwest')
ON CONFLICT ON CONSTRAINT uq_dim_sales_region_code DO UPDATE
SET sales_region_key = EXCLUDED.sales_region_key,
    sales_region_name = EXCLUDED.sales_region_name;

INSERT INTO mart_sales.dim_currency (
    currency_key,
    currency_code,
    currency_name,
    is_analysis_currency
)
VALUES
    (4001, 'CNY', 'Chinese Yuan', TRUE),
    (4002, 'USD', 'US Dollar', FALSE),
    (4003, 'EUR', 'Euro', FALSE)
ON CONFLICT ON CONSTRAINT uq_dim_currency_code DO UPDATE
SET currency_key = EXCLUDED.currency_key,
    currency_name = EXCLUDED.currency_name,
    is_analysis_currency = EXCLUDED.is_analysis_currency;

INSERT INTO mart_sales.fct_exchange_rate_daily (
    rate_date_key,
    currency_key,
    rate_to_cny,
    source_system,
    source_updated_at,
    loaded_at
)
SELECT
    date_row.date_key,
    currency.currency_key,
    CASE currency.currency_code
        WHEN 'CNY' THEN 1.0::NUMERIC(20, 8)
        WHEN 'USD' THEN (7.00 + (date_row.date_key % 20) / 100.0)::NUMERIC(20, 8)
        WHEN 'EUR' THEN (7.30 + (date_row.date_key % 20) / 100.0)::NUMERIC(20, 8)
    END,
    'chatbi_dev_seed_v1',
    TIMESTAMPTZ '2025-12-31 00:00:00+00',
    TIMESTAMPTZ '2025-12-31 00:00:00+00'
FROM mart_sales.dim_date AS date_row
CROSS JOIN mart_sales.dim_currency AS currency
WHERE currency.currency_code IN ('CNY', 'USD', 'EUR')
ON CONFLICT ON CONSTRAINT pk_fct_exchange_rate_daily DO UPDATE
SET rate_to_cny = EXCLUDED.rate_to_cny,
    source_system = EXCLUDED.source_system,
    source_updated_at = EXCLUDED.source_updated_at,
    loaded_at = EXCLUDED.loaded_at;

WITH orders AS (
    SELECT
        order_number,
        DATE '2024-01-01'
            + FLOOR((order_number - 1) * 699.0 / 499)::INTEGER AS order_date,
        CASE order_number % 10
            WHEN 7 THEN 'confirmed'
            WHEN 8 THEN 'pending'
            WHEN 9 THEN 'cancelled'
            ELSE 'completed'
        END AS order_status
    FROM generate_series(1, 500) AS order_rows(order_number)
),
order_lines AS (
    SELECT
        orders.order_number,
        line_number,
        orders.order_date,
        orders.order_status,
        CASE
            WHEN orders.order_status = 'pending' THEN NULL
            ELSE orders.order_date + (orders.order_number % 3) + 1
        END AS confirmation_date,
        CASE
            WHEN orders.order_status = 'completed'
                THEN orders.order_date + 3 + (orders.order_number % 10)
            ELSE NULL
        END AS completion_date,
        1001 + ((orders.order_number * 7) % 8) AS customer_key,
        2001 + ((orders.order_number * 3 + line_number * 5) % 8) AS product_key,
        3001 + ((orders.order_number * 5) % 6) AS sales_region_key,
        4001 + ((orders.order_number * 2 + line_number) % 3) AS currency_key,
        (1 + ((orders.order_number + line_number * 3) % 5))::NUMERIC(20, 6)
            AS quantity,
        (50 + ((orders.order_number * 37 + line_number * 113) % 951))::NUMERIC(20, 6)
            AS unit_price_transaction
    FROM orders
    CROSS JOIN LATERAL generate_series(1, 3) AS lines(line_number)
    WHERE line_number <= 2 + CASE WHEN orders.order_number % 3 = 0 THEN 1 ELSE 0 END
),
amounts AS (
    SELECT
        order_lines.*,
        quantity * unit_price_transaction AS gross_sales_amount,
        CASE
            WHEN order_number % 29 = 0 THEN quantity * unit_price_transaction
            ELSE quantity * unit_price_transaction
                * ((order_number + line_number) % 15) / 100.0
        END AS discount_amount,
        CASE
            WHEN order_number % 10 BETWEEN 0 AND 6
                THEN 0.35 + ((order_number + line_number * 3) % 26) / 100.0
            ELSE NULL
        END AS cost_rate
    FROM order_lines
),
converted AS (
    SELECT
        amounts.*,
        fx.rate_to_cny,
        CASE
            WHEN order_status = 'completed'
                THEN gross_sales_amount - discount_amount
            ELSE NULL
        END AS net_sales_amount_transaction
    FROM amounts
    LEFT JOIN mart_sales.fct_exchange_rate_daily AS fx
      ON fx.rate_date_key = to_char(completion_date, 'YYYYMMDD')::INTEGER
     AND fx.currency_key = amounts.currency_key
)
INSERT INTO mart_sales.fct_sales_order_line (
    sales_order_line_key,
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
    source_updated_at,
    loaded_at
)
SELECT
    2000000 + order_number * 10 + line_number,
    100000 + order_number,
    'DEV-' || LPAD(order_number::TEXT, 4, '0'),
    1000000 + order_number * 10 + line_number,
    line_number,
    customer_key,
    product_key,
    sales_region_key,
    currency_key,
    to_char(order_date, 'YYYYMMDD')::INTEGER,
    CASE
        WHEN confirmation_date IS NULL THEN NULL
        ELSE to_char(confirmation_date, 'YYYYMMDD')::INTEGER
    END,
    CASE
        WHEN completion_date IS NULL THEN NULL
        ELSE to_char(completion_date, 'YYYYMMDD')::INTEGER
    END,
    order_status,
    quantity,
    unit_price_transaction,
    discount_amount,
    gross_sales_amount,
    net_sales_amount_transaction,
    CASE WHEN order_status = 'completed' THEN rate_to_cny ELSE NULL END,
    CASE
        WHEN order_status = 'completed'
            THEN net_sales_amount_transaction * rate_to_cny
        ELSE NULL
    END,
    CASE
        WHEN order_status = 'completed'
            THEN net_sales_amount_transaction * rate_to_cny * cost_rate / quantity
        ELSE NULL
    END,
    CASE
        WHEN order_status = 'completed'
            THEN net_sales_amount_transaction * rate_to_cny * cost_rate
        ELSE NULL
    END,
    'chatbi_dev_seed_v1',
    TIMESTAMPTZ '2025-12-31 00:00:00+00',
    TIMESTAMPTZ '2025-12-31 00:00:00+00'
FROM converted
ON CONFLICT ON CONSTRAINT uq_fct_sales_order_line_id DO UPDATE
SET sales_order_line_key = EXCLUDED.sales_order_line_key,
    order_id = EXCLUDED.order_id,
    order_no = EXCLUDED.order_no,
    order_line_no = EXCLUDED.order_line_no,
    customer_key = EXCLUDED.customer_key,
    product_key = EXCLUDED.product_key,
    sales_region_key = EXCLUDED.sales_region_key,
    transaction_currency_key = EXCLUDED.transaction_currency_key,
    order_date_key = EXCLUDED.order_date_key,
    confirmation_date_key = EXCLUDED.confirmation_date_key,
    completion_date_key = EXCLUDED.completion_date_key,
    order_status = EXCLUDED.order_status,
    quantity = EXCLUDED.quantity,
    unit_price_transaction = EXCLUDED.unit_price_transaction,
    discount_amount_transaction = EXCLUDED.discount_amount_transaction,
    gross_sales_amount_transaction = EXCLUDED.gross_sales_amount_transaction,
    net_sales_amount_transaction = EXCLUDED.net_sales_amount_transaction,
    fx_rate_to_cny = EXCLUDED.fx_rate_to_cny,
    net_sales_amount_cny = EXCLUDED.net_sales_amount_cny,
    frozen_unit_cost_cny = EXCLUDED.frozen_unit_cost_cny,
    sales_cost_amount_cny = EXCLUDED.sales_cost_amount_cny,
    source_system = EXCLUDED.source_system,
    source_updated_at = EXCLUDED.source_updated_at,
    loaded_at = EXCLUDED.loaded_at;

SELECT setval(
    pg_get_serial_sequence('mart_sales.dim_customer', 'customer_key'),
    (SELECT MAX(customer_key) FROM mart_sales.dim_customer),
    TRUE
);
SELECT setval(
    pg_get_serial_sequence('mart_sales.dim_product', 'product_key'),
    (SELECT MAX(product_key) FROM mart_sales.dim_product),
    TRUE
);
SELECT setval(
    pg_get_serial_sequence('mart_sales.dim_sales_region', 'sales_region_key'),
    (SELECT MAX(sales_region_key) FROM mart_sales.dim_sales_region),
    TRUE
);
SELECT setval(
    pg_get_serial_sequence('mart_sales.dim_currency', 'currency_key'),
    (SELECT MAX(currency_key) FROM mart_sales.dim_currency),
    TRUE
);
SELECT setval(
    pg_get_serial_sequence('mart_sales.fct_sales_order_line', 'sales_order_line_key'),
    (SELECT MAX(sales_order_line_key) FROM mart_sales.fct_sales_order_line),
    TRUE
);

INSERT INTO mart_sales.dev_seed_metadata (singleton, seed_version, seeded_at)
VALUES (TRUE, 'chatbi-sales-mart-dev-v1', TIMESTAMPTZ '2025-12-31 00:00:00+00')
ON CONFLICT (singleton) DO UPDATE
SET seed_version = EXCLUDED.seed_version,
    seeded_at = EXCLUDED.seeded_at;
