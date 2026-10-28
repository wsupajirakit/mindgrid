#!/usr/bin/env bash
# One-time local setup: create the app role (LOGIN, no superuser, no BYPASSRLS, owns
# nothing) with a random password stored in the Keychain, and let it use both databases.
set -euo pipefail
PG_BIN="${MINDGRID_DEV_PG_BIN:-/opt/homebrew/opt/postgresql@18/bin}"
host="${MINDGRID_DEV_PG_HOST:-localhost}"; port="${MINDGRID_DEV_PG_PORT:-55432}"
owner="${MINDGRID_DEV_PG_OWNER:-mindgrid}"; app="${MINDGRID_DEV_PG_APP_ROLE:-mindgrid_app}"
owner_pw="$(security find-generic-password -s mindgrid -a dev-db -w)"
app_pw="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
security add-generic-password -U -s mindgrid -a dev-db-app -w "$app_pw"
export PGPASSWORD="$owner_pw"
"$PG_BIN/psql" -h "$host" -p "$port" -U "$owner" -d postgres -v ON_ERROR_STOP=1 -q \
  -v app="$app" -v pw="$app_pw" <<'SQL'
select format('create role %I login nosuperuser nobypassrls nocreatedb nocreaterole', :'app')
  where not exists (select from pg_roles where rolname = :'app') \gexec
select format('alter role %I password %L', :'app', :'pw') \gexec
SQL
for db in mindgrid_dev mindgrid_test; do
  "$PG_BIN/psql" -h "$host" -p "$port" -U "$owner" -d "$db" -v ON_ERROR_STOP=1 -q \
    -c "grant connect on database $db to $app; grant usage on schema public to $app;"
done
echo "app role ready; password in Keychain (mindgrid / dev-db-app)"
