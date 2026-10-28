"""Keep a family of playbooks (an id prefix, e.g. the market screens "markets.") switched on
only in the projects meant for it, and off everywhere else. Nothing is deleted: it only
changes on/off choices. Without --apply it prints what it would change.

For each playbook of the family: projects outside --keep that run it get their own "off";
--keep projects that run it only through the system switch get their own "on"; then the
system switch goes off, so a project made later does not inherit the family.

  backend/.venv/bin/python tools/playbook_scope.py --server https://mindgrid.example.com \\
      --email admin@example.com --prefix markets. --keep us-stock-radar [--apply]

The admin password comes from MINDGRID_ADMIN_PASSWORD or a prompt.
"""

import argparse
import getpass
import os
import sys
from dataclasses import dataclass, field
from typing import Any

import mgapi


@dataclass
class Plan:
    playbook_id: str
    system_on: bool
    running: list[str]  # project slugs where it runs today
    choices: dict[str, bool] = field(default_factory=dict[str, bool])  # project id -> on/off

    def changes(self) -> bool:
        return self.system_on or bool(self.choices)


def _plan(api: mgapi.Client, playbook_id: str, slugs: dict[str, str], keep: set[str]) -> Plan:
    found: dict[str, Any] = api.call("GET", f"playbooks/{playbook_id}/assignments")
    plan = Plan(playbook_id, bool(found["all_projects"]), [])
    for p in found["projects"]:
        slug = slugs.get(p["project_id"], p["name"])
        if p["enabled"]:
            plan.running.append(slug)
        if p["enabled"] and slug not in keep:
            plan.choices[p["project_id"]] = False
        elif p["enabled"] and not p["own_choice"]:
            plan.choices[p["project_id"]] = True  # keep it when the system switch goes off
    return plan


def _report(plan: Plan, names: dict[str, str]) -> None:
    off = [names[k] for k, v in plan.choices.items() if not v]
    kept = [names[k] for k, v in plan.choices.items() if v]
    print(
        f"{plan.playbook_id:28} system {'ON ' if plan.system_on else 'off'} "
        f"runs in: {', '.join(plan.running) or '-'}"
    )
    if off:
        print(f"{'':28} -> off in: {', '.join(off)}")
    if kept:
        print(f"{'':28} -> own 'on' kept in: {', '.join(kept)}")
    if plan.system_on:
        print(f"{'':28} -> system switch off")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--server", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--prefix", required=True, help="Playbook id prefix, e.g. markets.")
    parser.add_argument(
        "--keep", action="append", required=True, help="Project slug allowed (repeatable)"
    )
    parser.add_argument("--apply", action="store_true", help="Make the changes")
    args = parser.parse_args()
    api = mgapi.Client(args.server)
    password = os.environ.get("MINDGRID_ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
    api.sign_in(args.email, password)
    projects = api.call("GET", "projects")
    slugs = {str(p["id"]): p["slug"] for p in projects}
    missing = set(args.keep) - set(slugs.values())
    if missing:
        raise SystemExit(f"no such project: {', '.join(sorted(missing))}")
    family = [p["id"] for p in api.call("GET", "playbooks") if p["id"].startswith(args.prefix)]
    if not family:
        raise SystemExit(f"no playbook id starts with {args.prefix!r}")
    plans = [_plan(api, pid, slugs, set(args.keep)) for pid in family]
    for plan in plans:
        _report(plan, slugs)
    todo = [p for p in plans if p.changes()]
    if not todo:
        print(f"\nok: {args.prefix}* runs only in {', '.join(args.keep)}")
        return
    if not args.apply:
        print(f"\n{len(todo)} playbook(s) to change; run again with --apply")
        return
    for plan in todo:
        body = {"all_projects": False if plan.system_on else None, "projects": plan.choices}
        api.call("PUT", f"playbooks/{plan.playbook_id}/assignments", body)
    again = [_plan(api, pid, slugs, set(args.keep)) for pid in family]
    left = [p.playbook_id for p in again if p.changes()]
    if left:
        raise SystemExit(f"still not in scope: {', '.join(left)}")
    print(f"\napplied: {args.prefix}* now runs only in {', '.join(args.keep)}")


if __name__ == "__main__":
    sys.exit(main())
