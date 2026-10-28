#!/usr/bin/env bash
# Gate for every commit: every check must pass, otherwise nothing is committed.
#   tools/gate.sh "<commit message>" [paths to add...]     (default path: the whole repo)
#   tools/gate.sh --check                                  (run the checks only)
set -euo pipefail
usage() { sed -n '2,4p' "$0" | sed 's/^# \{0,1\}//'; }
if [ $# -eq 0 ] || [ -z "${1// /}" ]; then usage; exit 2; fi
cd "$(git rev-parse --show-toplevel)"
# Database tests are part of every gate run: use the CI-provided URL, else the dev setup.
if [ -z "${MINDGRID_TEST_DATABASE_URL:-}" ] && [ -f tools/dev_env.sh ]; then
  # shellcheck source=/dev/null
  source tools/dev_env.sh
fi
export MINDGRID_REQUIRE_DB=1
PY=backend/.venv/bin/python
backend/.venv/bin/ruff check .
backend/.venv/bin/ruff format --check .
(cd backend && .venv/bin/pyright)
python3 tools/check_structure.py
python3 tools/check_notes.py
python3 tools/check_private.py
python3 tools/check_brand.py
$PY tools/config_reference.py --check
# Every migration must also downgrade: round-trip the test database before the tests.
(cd backend && export MINDGRID_MIGRATION_DATABASE_URL="$MINDGRID_TEST_MIGRATION_DATABASE_URL" \
  && .venv/bin/alembic -q downgrade base && .venv/bin/alembic -q upgrade head)
(cd backend && nice -n 15 .venv/bin/python -m pytest)
$PY tools/export_openapi.py --check
$PY tools/postman_collection.py --check
# A changed lock file must also be free of known advisories (needs the network).
if [ -n "$(git status --porcelain -- backend/uv.lock)" ]; then python3 tools/osv_audit.py; fi
if [ -n "$(git status --porcelain -- web/package-lock.json)" ]; then
  (cd web && npm audit --audit-level=low)
fi
# Web: types, lint, i18n, tests, build, budget. Quiet when green, the full log when not.
web_log="$(mktemp)"
if ! (cd web && nice -n 15 npm run verify >"$web_log" 2>&1); then cat "$web_log"; exit 1; fi
rm -f "$web_log"
[ "$1" = "--check" ] && exit 0
if [ "${1#-}" != "$1" ]; then usage; exit 2; fi
msg="$1"; shift
paths=("${@:-.}")
git add -- "${paths[@]}"
git commit -q -m "$msg" -- "${paths[@]}"
if git remote get-url origin >/dev/null 2>&1; then git push -q; fi
git log --oneline -1
