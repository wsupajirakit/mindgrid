#!/usr/bin/env bash
# Source this for local development: `source tools/dev_env.sh`. Builds the database URLs
# from passwords kept in the macOS Keychain (service "mindgrid"), never from files.
#   accounts: dev-db (owner role), dev-db-app (app role, created by tools/dev_db_init.sh)
# Override host/port/names with MINDGRID_DEV_PG_HOST / _PORT / _OWNER / _APP_ROLE.
_mg_secret() { security find-generic-password -s mindgrid -a "$1" -w 2>/dev/null; }
_mg_host="${MINDGRID_DEV_PG_HOST:-localhost}"
_mg_port="${MINDGRID_DEV_PG_PORT:-55432}"
_mg_owner="${MINDGRID_DEV_PG_OWNER:-mindgrid}"
_mg_app="${MINDGRID_DEV_PG_APP_ROLE:-mindgrid_app}"
_mg_owner_pw="$(_mg_secret dev-db)"
_mg_app_pw="$(_mg_secret dev-db-app)"
_mg_url() { printf 'postgresql+asyncpg://%s:%s@%s:%s/%s' "$1" "$2" "$_mg_host" "$_mg_port" "$3"; }
export MINDGRID_DB_APP_ROLE="$_mg_app"
export MINDGRID_DATABASE_URL="$(_mg_url "$_mg_app" "$_mg_app_pw" mindgrid_dev)"
export MINDGRID_MIGRATION_DATABASE_URL="$(_mg_url "$_mg_owner" "$_mg_owner_pw" mindgrid_dev)"
export MINDGRID_TEST_DATABASE_URL="$(_mg_url "$_mg_app" "$_mg_app_pw" mindgrid_test)"
export MINDGRID_TEST_MIGRATION_DATABASE_URL="$(_mg_url "$_mg_owner" "$_mg_owner_pw" mindgrid_test)"
unset _mg_owner_pw _mg_app_pw
