#!/bin/sh
set -eu

pg_isready --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" >/dev/null

business_ready=$(
    psql \
        --username "$POSTGRES_USER" \
        --dbname "$POSTGRES_DB" \
        --set ON_ERROR_STOP=1 \
        --tuples-only \
        --no-align \
        --command "
            SELECT 1
            FROM mart_sales.dev_seed_metadata
            WHERE singleton
              AND seed_version = 'chatbi-sales-mart-dev-v1'
              AND EXISTS (SELECT 1 FROM mart_sales.fct_sales_order_line)
              AND has_schema_privilege('chatbi_app', 'mart_sales', 'USAGE')
              AND has_table_privilege(
                    'chatbi_app',
                    'mart_sales.fct_sales_order_line',
                    'SELECT'
                  )
              AND NOT has_table_privilege(
                    'chatbi_app',
                    'mart_sales.fct_sales_order_line',
                    'INSERT'
                  )
              AND NOT has_database_privilege(
                    'chatbi_control_user',
                    'chatbi_mvp',
                    'CONNECT'
                  )
              AND NOT has_database_privilege(
                    'chatbi_control_user',
                    'postgres',
                    'CONNECT'
                  )
              AND NOT has_database_privilege(
                    'chatbi_app',
                    'chatbi_control',
                    'CONNECT'
                  )
              AND NOT has_database_privilege(
                    'chatbi_app',
                    'postgres',
                    'CONNECT'
                  )
        "
)
[ "$business_ready" = "1" ]

control_ready=$(
    psql \
        --username "$POSTGRES_USER" \
        --dbname "$POSTGRES_CONTROL_DB" \
        --set ON_ERROR_STOP=1 \
        --tuples-only \
        --no-align \
        --command "
            SELECT 1
            FROM schema_migrations
            WHERE version = 'chatbi-control-v1'
              AND (SELECT count(*) FROM roles) >= 2
              AND (SELECT count(*) FROM permissions) >= 4
              AND has_database_privilege(
                    'chatbi_control_user',
                    'chatbi_control',
                    'CONNECT'
                  )
              AND has_table_privilege('chatbi_control_user', 'users', 'INSERT')
              AND NOT has_table_privilege('chatbi_control_user', 'users', 'DELETE')
              AND NOT (
                    SELECT rolsuper
                    FROM pg_roles
                    WHERE rolname = 'chatbi_control_user'
                  )
        "
)
[ "$control_ready" = "1" ]
