-- Course Baseline V1 的最小只读应用权限。
-- 凭据从 Compose 环境读取，不写入仓库，也不在 SQL 输出中打印。

\set ON_ERROR_STOP on
\getenv app_user POSTGRES_APP_USER
\getenv app_password POSTGRES_APP_PASSWORD

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'app_user', :'app_password')
WHERE NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = :'app_user'
)
\gexec

ALTER ROLE :"app_user"
    WITH LOGIN PASSWORD :'app_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM :"app_user";
GRANT USAGE ON SCHEMA public TO :"app_user";

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM :"app_user";
GRANT SELECT ON TABLE
    public.dim_customers,
    public.dim_products,
    public.sales_orders,
    public.exchange_rates,
    public.finance_expenses
TO :"app_user";

REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM :"app_user";
