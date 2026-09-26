-- ChatBI 应用账号对当前 Sales Mart（销售集市）的只读权限。
-- 只授予 Schema 使用权和现有业务表 SELECT，不授予写入、建表或建库权限。
\set ON_ERROR_STOP on

REVOKE CONNECT ON DATABASE chatbi_mvp FROM PUBLIC;
GRANT CONNECT ON DATABASE chatbi_mvp TO chatbi_app;
GRANT USAGE ON SCHEMA mart_sales TO chatbi_app;
GRANT SELECT ON ALL TABLES IN SCHEMA mart_sales TO chatbi_app;
