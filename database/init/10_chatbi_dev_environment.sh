#!/bin/sh
set -eu

: "${POSTGRES_APP_USER:?POSTGRES_APP_USER is required}"
: "${POSTGRES_APP_PASSWORD:?POSTGRES_APP_PASSWORD is required}"
: "${POSTGRES_CONTROL_DB:?POSTGRES_CONTROL_DB is required}"
: "${POSTGRES_CONTROL_APP_USER:?POSTGRES_CONTROL_APP_USER is required}"
: "${POSTGRES_CONTROL_APP_PASSWORD:?POSTGRES_CONTROL_APP_PASSWORD is required}"
: "${POSTGRES_CONTROL_MIGRATOR_USER:?POSTGRES_CONTROL_MIGRATOR_USER is required}"

if [ "$POSTGRES_APP_USER" != "chatbi_app" ]; then
    echo "POSTGRES_APP_USER must be chatbi_app for the Sales Mart grants." >&2
    exit 1
fi
if [ "$POSTGRES_CONTROL_APP_USER" != "chatbi_control_user" ]; then
    echo "POSTGRES_CONTROL_APP_USER must be chatbi_control_user for the Control DB grants." >&2
    exit 1
fi
if [ "$POSTGRES_CONTROL_DB" != "chatbi_control" ]; then
    echo "POSTGRES_CONTROL_DB must be chatbi_control for the Control DB grants." >&2
    exit 1
fi
if [ "$POSTGRES_CONTROL_MIGRATOR_USER" != "$POSTGRES_USER" ]; then
    echo "POSTGRES_CONTROL_MIGRATOR_USER must match POSTGRES_MIGRATOR_USER during local initialization." >&2
    exit 1
fi

psql \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --set ON_ERROR_STOP=1 \
    --set "business_db=$POSTGRES_DB" \
    --set "app_user=$POSTGRES_APP_USER" \
    --set "app_password=$POSTGRES_APP_PASSWORD" \
    --set "control_app_user=$POSTGRES_CONTROL_APP_USER" \
    --set "control_app_password=$POSTGRES_CONTROL_APP_PASSWORD" \
    --file /workspace/database/init/00_create_runtime_roles.sql

psql \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --set ON_ERROR_STOP=1 \
    --file /workspace/database/sales_mart/001_create_schema.sql

psql \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --set ON_ERROR_STOP=1 \
    --file /workspace/database/dev/seed_sales_mart.sql

psql \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --set ON_ERROR_STOP=1 \
    --file /workspace/database/grants.sql

createdb \
    --username "$POSTGRES_USER" \
    --owner "$POSTGRES_USER" \
    "$POSTGRES_CONTROL_DB"

for migration in \
    /workspace/database/control/001_schema.sql \
    /workspace/database/control/002_seed_rbac.sql \
    /workspace/database/control/003_grants.sql
do
    psql \
        --username "$POSTGRES_USER" \
        --dbname "$POSTGRES_CONTROL_DB" \
        --set ON_ERROR_STOP=1 \
        --file "$migration"
done
