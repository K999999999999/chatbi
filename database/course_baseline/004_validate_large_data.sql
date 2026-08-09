-- Course Baseline V1 大数据模式：质量和业务场景验证 SQL。
-- 本文件只查询，不修改表结构和数据。

-- 基础质量
SELECT COUNT(*) AS customer_orphans
FROM public.sales_orders o
LEFT JOIN public.dim_customers c ON c.customer_id = o.customer_id
WHERE c.customer_id IS NULL;

SELECT COUNT(*) AS product_orphans
FROM public.sales_orders o
LEFT JOIN public.dim_products p ON p.product_id = o.product_id
WHERE p.product_id IS NULL;

SELECT COUNT(*) AS duplicate_order_no_groups
FROM (
    SELECT order_no FROM public.sales_orders
    GROUP BY order_no HAVING COUNT(*) > 1
) duplicates;

SELECT COUNT(*) AS missing_order_rates
FROM public.sales_orders o
LEFT JOIN public.exchange_rates er
  ON er.rate_date = o.order_date AND er.currency = o.currency
WHERE er.currency IS NULL;

SELECT COUNT(*) AS cny_rate_errors
FROM public.exchange_rates
WHERE currency = 'CNY' AND rate_to_cny <> 1;

SELECT COUNT(*) AS invalid_order_amounts
FROM public.sales_orders
WHERE quantity <= 0
   OR unit_price <= 0
   OR discount_amount < 0
   OR net_amount <= 0
   OR gross_amount < net_amount;

SELECT COUNT(*) AS selling_expense_subitem_overflow
FROM public.finance_expenses
WHERE selling_expense < marketing_expense + logistics_expense + warranty_expense;

-- 场景 1：2024～2026 年人民币完成收入趋势
SELECT EXTRACT(YEAR FROM o.order_date)::INT AS year,
       ROUND(SUM(o.net_amount * er.rate_to_cny), 2) AS revenue_rmb
FROM public.sales_orders o
JOIN public.exchange_rates er
  ON er.rate_date = o.order_date AND er.currency = o.currency
WHERE o.order_status = 'completed'
GROUP BY year
ORDER BY year;

-- 场景 2：动力电池-商用车 2026 Q2 相比 2025 Q2 的收入变化
SELECT EXTRACT(YEAR FROM o.order_date)::INT AS year,
       EXTRACT(QUARTER FROM o.order_date)::INT AS quarter,
       ROUND(SUM(o.net_amount * er.rate_to_cny), 2) AS revenue_rmb
FROM public.sales_orders o
JOIN public.dim_products p ON p.product_id = o.product_id
JOIN public.exchange_rates er
  ON er.rate_date = o.order_date AND er.currency = o.currency
WHERE o.order_status = 'completed'
  AND p.product_line = '动力电池-商用车'
  AND o.order_date >= DATE '2025-04-01'
  AND o.order_date < DATE '2026-07-01'
GROUP BY year, quarter
ORDER BY year, quarter;

-- 场景 3：产品线毛利率，课程成本口径为 material_cost + labor_cost
SELECT EXTRACT(YEAR FROM o.order_date)::INT AS year,
       EXTRACT(QUARTER FROM o.order_date)::INT AS quarter,
       p.product_line,
       ROUND(
           SUM(o.net_amount - (p.material_cost + p.labor_cost) * o.quantity)
           / NULLIF(SUM(o.net_amount), 0), 4
       ) AS gross_margin_rate
FROM public.sales_orders o
JOIN public.dim_products p ON p.product_id = o.product_id
WHERE o.order_status = 'completed'
GROUP BY year, quarter, p.product_line
ORDER BY year, quarter, p.product_line;

-- 场景 4：客户区域人民币收入增长差异
SELECT c.region,
       EXTRACT(YEAR FROM o.order_date)::INT AS year,
       ROUND(SUM(o.net_amount * er.rate_to_cny), 2) AS revenue_rmb
FROM public.sales_orders o
JOIN public.dim_customers c ON c.customer_id = o.customer_id
JOIN public.exchange_rates er
  ON er.rate_date = o.order_date AND er.currency = o.currency
WHERE o.order_status = 'completed'
GROUP BY c.region, year
ORDER BY c.region, year;

-- 场景 5：2026 Q2 研发费用、2026 Q3 销售费用异常
SELECT EXTRACT(YEAR FROM expense_date)::INT AS year,
       EXTRACT(QUARTER FROM expense_date)::INT AS quarter,
       SUM(rd_expense) AS rd_expense,
       SUM(selling_expense) AS selling_expense
FROM public.finance_expenses
GROUP BY year, quarter
ORDER BY year, quarter;

-- 客户区域与销售区域保持两个语义，允许跨区域销售
SELECT COUNT(*) FILTER (WHERE c.region = o.region) AS same_region_orders,
       COUNT(*) FILTER (WHERE c.region <> o.region) AS cross_region_orders,
       COUNT(*) AS total_orders
FROM public.sales_orders o
JOIN public.dim_customers c ON c.customer_id = o.customer_id;

-- 课程人民币收入逻辑：不增加 sales_amount_cny，运行时通过汇率 Join 计算。
SELECT ROUND(SUM(o.net_amount * er.rate_to_cny), 2) AS completed_revenue_rmb
FROM public.sales_orders o
JOIN public.dim_customers c ON c.customer_id = o.customer_id
JOIN public.exchange_rates er
  ON er.rate_date = o.order_date AND er.currency = o.currency
WHERE o.order_status = 'completed';

