#!/bin/sh
set -eu

attempt=0
while [ "$attempt" -lt 120 ]; do
    if pg_isready --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" >/dev/null; then
        business_ready=$(
            psql \
                --username "$POSTGRES_USER" \
                --dbname "$POSTGRES_DB" \
                --set ON_ERROR_STOP=1 \
                --tuples-only \
                --no-align \
                --command "SELECT 1 FROM mart_sales.dev_seed_metadata WHERE singleton AND seed_version = 'chatbi-sales-mart-dev-v3'" \
                2>/dev/null || true
        )
        control_ready=$(
            psql \
                --username "$POSTGRES_USER" \
                --dbname "$POSTGRES_CONTROL_DB" \
                --set ON_ERROR_STOP=1 \
                --tuples-only \
                --no-align \
                --command "SELECT 1 FROM schema_migrations WHERE version = 'chatbi-control-v2'" \
                2>/dev/null || true
        )
        if [ "$business_ready" = "1" ] && [ "$control_ready" = "1" ]; then
            exit 0
        fi
    fi
    attempt=$((attempt + 1))
    sleep 1
done

echo "PostgreSQL base initialization did not complete within 120 seconds." >&2
exit 1
