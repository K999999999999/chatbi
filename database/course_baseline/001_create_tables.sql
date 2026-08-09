-- 第 4 课 Course Baseline V1：PostgreSQL 建表脚本。
-- 业务模型严格保留课程的 5 张核心表，不增加数仓代理键、日期维度或指标字段。

BEGIN;

DROP TABLE IF EXISTS public.sales_orders;
DROP TABLE IF EXISTS public.exchange_rates;
DROP TABLE IF EXISTS public.finance_expenses;
DROP TABLE IF EXISTS public.dim_products;
DROP TABLE IF EXISTS public.dim_customers;

CREATE TABLE public.dim_customers (
    customer_id INT PRIMARY KEY,
    customer_name VARCHAR(100) NOT NULL,
    customer_type VARCHAR(50),
    industry VARCHAR(50),
    country VARCHAR(50),
    region VARCHAR(50)
);

CREATE TABLE public.dim_products (
    product_id INT PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL,
    product_line VARCHAR(50),
    category VARCHAR(50),
    tech_route VARCHAR(50),
    standard_cost DECIMAL(10, 2),
    material_cost DECIMAL(10, 2),
    labor_cost DECIMAL(10, 2)
);

CREATE TABLE public.sales_orders (
    order_id BIGINT PRIMARY KEY,
    order_no VARCHAR(50) UNIQUE,
    customer_id INT,
    product_id INT,
    region VARCHAR(50),
    order_date DATE,
    order_status VARCHAR(20),
    quantity DECIMAL(10, 2),
    unit_price DECIMAL(10, 2),
    discount_amount DECIMAL(10, 2),
    gross_amount DECIMAL(12, 2),
    net_amount DECIMAL(12, 2),
    currency VARCHAR(10),
    CONSTRAINT fk_sales_orders_customer
        FOREIGN KEY (customer_id) REFERENCES public.dim_customers(customer_id),
    CONSTRAINT fk_sales_orders_product
        FOREIGN KEY (product_id) REFERENCES public.dim_products(product_id)
);

CREATE TABLE public.exchange_rates (
    rate_date DATE,
    currency VARCHAR(10),
    rate_to_cny DECIMAL(10, 4),
    PRIMARY KEY (rate_date, currency)
);

CREATE TABLE public.finance_expenses (
    expense_id BIGINT PRIMARY KEY,
    expense_date DATE,
    department VARCHAR(50),
    rd_expense DECIMAL(12, 2),
    selling_expense DECIMAL(12, 2),
    admin_expense DECIMAL(12, 2),
    finance_expense DECIMAL(12, 2),
    marketing_expense DECIMAL(12, 2),
    logistics_expense DECIMAL(12, 2),
    warranty_expense DECIMAL(12, 2)
);

COMMIT;

