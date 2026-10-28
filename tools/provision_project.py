"""Provision a complete market-data project through the API, safe to run again.

What it sets up (each step skips what already exists):
  1. the project;
  2. the data service key as an encrypted project secret;
  3. a connector built from the server's data-service template (every timeframe and the
     formula sheet, synced hourly), then a first sync;
  4. every playbook in the catalog, switched on for the project;
  5. optionally a knowledge category with methodology documents (--doc, repeatable);
  6. optionally an API key for MCP and scripts, limited to this project; its private key
     goes to a client profile file readable only by you and is never printed;
  7. one run of each playbook on the synced data, with its result.

Credentials are never printed. The admin password comes from MINDGRID_ADMIN_PASSWORD or a
prompt; the data service key from MINDGRID_DATA_KEY, a macOS Keychain item
(--data-key-keychain SERVICE/ACCOUNT) or a prompt.

  backend/.venv/bin/python tools/provision_project.py --server https://mindgrid.example.com \\
      --email admin@example.com --data-url https://data.example.com \\
      --data-key-keychain z-service/env:PULL_KEY --issue-key --profile markets
"""

import argparse
import getpass
import os
import sys
from pathlib import Path
from typing import Any

import mgapi

VAULT_ENTRY = "connector.zservice.token"  # name of the project secret, not its value
TEMPLATE = "zservice-exports"
CONNECTOR = "zservice"


def _data_key(args: argparse.Namespace) -> str:
    if os.environ.get("MINDGRID_DATA_KEY"):
        return os.environ["MINDGRID_DATA_KEY"]
    if args.data_key_keychain:
        return mgapi.secret_from_keychain(args.data_key_keychain)
    return getpass.getpass("Data service key: ")


def _connector(api: mgapi.Client, pid: str, data_url: str, every: int) -> None:
    template = next(t for t in api.call("GET", "connector-templates") if t["id"] == TEMPLATE)
    spec = dict(template["spec"])
    spec["base_url"] = data_url.rstrip("/")
    spec["auth"] = {"type": "header", "name": "X-Pull-Key", "secret": VAULT_ENTRY}
    mgapi.save_connector(api, pid, CONNECTOR, spec, every)


def _playbooks(api: mgapi.Client, pid: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = api.call("GET", "playbooks") or []
    for p in rows:
        body = {"enabled": True, "params": {}, "version": None}
        api.call("PUT", f"projects/{pid}/playbooks/{p['id']}", body)
    print(f"playbooks    {len(rows)} switched on: {', '.join(p['id'] for p in rows)}")
    return rows


def _knowledge(api: mgapi.Client, pid: str, docs: list[Path]) -> None:
    if not docs:
        return
    cat = mgapi.ensure_category(api, pid, "methodology", "Methodology", "Rules behind playbooks.")
    for doc in docs:
        media = "application/pdf" if doc.suffix.lower() == ".pdf" else "text/markdown"
        mgapi.upload_document(api, cat, mgapi.Upload(doc.stem, doc.name, doc.read_bytes(), media))
    print(f"knowledge    category Methodology: {len(docs)} document(s)")


def _runs(api: mgapi.Client, pid: str, playbooks: list[dict[str, Any]]) -> None:
    extra = mgapi.generic_runs(api, pid, "bars-1d-part1")
    for p in playbooks:
        params, inputs = extra.get(p["id"], ({}, {}))
        run = mgapi.run_playbook(api, pid, p, params, inputs)
        count = mgapi.result_count(run)
        print(f"run          {p['id']}: {run['status']} {count} {run.get('error', '')[:120]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--server", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--data-url", required=True, help="Data service base URL")
    parser.add_argument("--data-key-keychain", default="", help="SERVICE/ACCOUNT")
    parser.add_argument("--slug", default="us-stock-radar")
    parser.add_argument("--name", default="US Stock Radar")
    parser.add_argument(
        "--description",
        default="US market screens on live bars from the data service: multi-timeframe stage "
        "screen, near-pivot readiness, high conviction and coiled spring, refreshed hourly.",
    )
    parser.add_argument("--every", type=int, default=60, help="Sync interval in minutes")
    parser.add_argument("--wait", type=int, default=30, help="Minutes to wait for the sync")
    parser.add_argument("--doc", type=Path, action="append", default=[])
    parser.add_argument("--issue-key", action="store_true")
    parser.add_argument("--profile", default="markets")
    parser.add_argument("--key-days", type=int, default=90)
    parser.add_argument("--skip-sync", action="store_true", help="Data already synced")
    parser.add_argument("--skip-runs", action="store_true")
    args = parser.parse_args()
    api = mgapi.Client(args.server)
    password = os.environ.get("MINDGRID_ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
    me = api.sign_in(args.email, password)
    pid = mgapi.ensure_project(api, args.slug, args.name, args.description)
    api.call("PUT", f"projects/{pid}/secrets/{VAULT_ENTRY}", {"value": _data_key(args)})
    print(f"secret       {VAULT_ENTRY} stored (encrypted)")
    _connector(api, pid, args.data_url, args.every)
    if not args.skip_sync:
        mgapi.sync(api, pid, CONNECTOR, args.wait)
    playbooks = _playbooks(api, pid)
    _knowledge(api, pid, args.doc)
    if args.issue_key:
        want = mgapi.KeyRequest(me["id"], pid, f"{args.slug} client", args.profile, args.key_days)
        mgapi.issue_project_key(api, want)
    if not args.skip_runs:
        _runs(api, pid, playbooks)
    sys.stdout.flush()
    print(f"done         {api.server}/projects/{pid}")


if __name__ == "__main__":
    sys.exit(main())
