-- 第 4 课 Course Baseline V1：PostgreSQL 结构检查和 5 类课程验证 SQL。
-- 本文件不增加约束，只验证课程模型是否可用。

-- 结构检查
SELECT COUNT(*) AS table_count
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE';

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- 外键孤儿检查
SELECT COUNT(*) AS customer_orphans
FROM public.sales_orders o
LEFT JOIN public.dim_customers c ON c.customer_id = o.customer_id
WHERE c.customer_id IS NULL;

SELECT COUNT(*) AS product_orphans
FROM public.sales_orders o
LEFT JOIN public.dim_products p ON p.product_id = o.product_id
WHERE p.product_id IS NULL;

-- 订单号和汇率覆盖检查
SELECT COUNT(*) AS duplicate_order_no_groups
FROM (
    SELECT order_no
    FROM public.sales_orders
    GROUP BY order_no
    HAVING COUNT(*) > 1
) duplicates;

SELECT COUNT(*) AS missing_order_rates
FROM public.sales_orders o
LEFT JOIN public.exchange_rates er
  ON er.rate_date = o.order_date
 AND er.currency = o.currency
WHERE er.currency IS NULL;

SELECT COUNT(*) AS cny_rate_errors
FROM public.exchange_rates
WHERE currency = 'CNY'
  AND rate_to_cny <> 1;

-- 验证 1：按订单状态统计
SELECT
    order_status,
    COUNT(*) AS order_count,
    SUM(net_amount) AS total_net_amount
FROM public.sales_orders
GROUP BY order_status
ORDER BY order_status;

-- 验证 2：按产品线汇总收入
SELECT
    p.product_line,
    COUNT(DISTINCT o.order_id) AS order_count,
    SUM(o.quantity) AS total_quantity,
    SUM(o.net_amount) AS total_revenue
FROM public.sales_orders o
JOIN public.dim_products p ON o.product_id = p.product_id
WHERE o.order_status = 'completed'
GROUP BY p.product_line
ORDER BY p.product_line;

-- 验证 3：按客户区域汇总人民币收入
SELECT
    c.region,
    SUM(o.net_amount * er.rate_to_cny) AS revenue_rmb,
    COUNT(*) AS order_count
FROM public.sales_orders o
JOIN public.dim_customers c ON o.customer_id = c.customer_id
JOIN public.exchange_rates er
  ON o.order_date = er.rate_date
 AND o.currency = er.currency
WHERE o.order_status = 'completed'
GROUP BY c.region
ORDER BY revenue_rmb DESC;

-- 验证 4：按产品线计算毛利
SELECT
    p.product_line,
    SUM(o.net_amount) AS revenue,
    SUM((p.material_cost + p.labor_cost) * o.quantity) AS product_cost,
    SUM(o.net_amount - (p.material_cost + p.labor_cost) * o.quantity) AS gross_profit,
    SUM(o.net_amount - (p.material_cost + p.labor_cost) * o.quantity)
        / NULLIF(SUM(o.net_amount), 0) AS gross_margin_rate
FROM public.sales_orders o
JOIN public.dim_products p ON o.product_id = p.product_id
WHERE o.order_status = 'completed'
GROUP BY p.product_line
ORDER BY p.product_line;

-- 验证 5：按月汇总费用，PostgreSQL 使用 date_trunc 替代 DATE_FORMAT
SELECT
    date_trunc('month', expense_date)::DATE AS month,
    SUM(rd_expense) AS total_rd,
    SUM(selling_expense) AS total_selling,
    SUM(admin_expense) AS total_admin,
    SUM(finance_expense) AS total_finance
FROM public.finance_expenses
GROUP BY date_trunc('month', expense_date)::DATE
ORDER BY month;

