"""Run every playbook switched on in a project, several times, on the project's own data.

Each run is a real run (kept with who ran it, its inputs and outputs). Playbooks with a
`top_n` parameter cycle through a few row counts; the built-in screens (core.*) screen the
project's first dataset on its first numeric column. Runs go one at a time, so the worker
stays free for other work between them.

  backend/.venv/bin/python tools/run_playbooks.py --server https://mindgrid.example.com \\
      --email admin@example.com --project us-stock-radar --times 15

The admin password comes from MINDGRID_ADMIN_PASSWORD or a prompt. Needs the worker.
"""

import argparse
import getpass
import os
import sys
from collections import Counter
from typing import Any

import mgapi

ROW_COUNTS = (10, 20, 30, 50)


def _project(api: mgapi.Client, slug: str) -> str:
    for p in api.call("GET", "projects"):
        if p["slug"] == slug:
            return str(p["id"])
    raise SystemExit(f"no such project: {slug}")


def _plan(
    api: mgapi.Client, pid: str, playbooks: list[dict[str, Any]]
) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    """Parameters and inputs each playbook runs with (built-in screens need a dataset)."""
    if not any(p["id"].startswith("core.") for p in playbooks):
        return {}
    sets = api.call("GET", f"projects/{pid}/datasets")
    if not sets:
        raise SystemExit("the built-in screens need a dataset: sync the project first")
    return mgapi.generic_runs(api, pid, sets[0]["name"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--server", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--project", required=True, help="Project slug")
    parser.add_argument("--times", type=int, default=10, help="Runs per playbook (1-50)")
    args = parser.parse_args()
    if not 1 <= args.times <= 50:
        raise SystemExit("--times must be between 1 and 50")
    api = mgapi.Client(args.server)
    password = os.environ.get("MINDGRID_ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
    api.sign_in(args.email, password)
    pid = _project(api, args.project)
    playbooks = [p for p in api.call("GET", f"playbooks?project_id={pid}") if p["enabled"]]
    if not playbooks:
        raise SystemExit(f"{args.project} has no playbook switched on")
    extra = _plan(api, pid, playbooks)
    tally: Counter[str] = Counter()
    for i in range(args.times):
        for p in playbooks:
            params, inputs = extra.get(p["id"], ({}, {}))
            if "top_n" in p["param_names"]:
                params = {**params, "top_n": ROW_COUNTS[i % len(ROW_COUNTS)]}
            run = mgapi.run_playbook(api, pid, p, params, inputs)
            tally[run["status"]] += 1
            print(
                f"{i + 1:>2}/{args.times} {p['id']:28} {run['status']:8} "
                f"{mgapi.result_count(run)} {run.get('error', '')[:100]}",
                flush=True,
            )
    summary = ", ".join(f"{n} {status}" for status, n in sorted(tally.items()))
    print(f"\n{sum(tally.values())} runs in {args.project}: {summary}")
    if tally["done"] != sum(tally.values()):
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
