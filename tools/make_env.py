#!/usr/bin/env python3
"""Make a ready-to-paste production env from deploy/env.full.example, without a secret ever
reaching the screen, shell history or argv.

  python3 tools/make_env.py --public-url https://mindgrid.example.com

* DB_OWNER_PASSWORD, DB_APP_PASSWORD and MINDGRID_SECRET_KEY are random (48 bytes) and kept
  in the macOS Keychain (service "mindgrid", account "<profile>:<NAME>"). A later run reuses
  them, so the database password keeps matching the existing volume; --rotate makes new ones
  (the database role passwords must then be changed too, see docs/runbook.md).
* Other mock values (logo, tagline, internal hosts, ...) become blank, which means the
  default; --set NAME=VALUE fills any variable.
* The result goes to the clipboard (one KEY=VALUE per line, no comments: hosting panels
  read an inline comment as part of the value), or to a 0600 file with --write.
* Only names, sizes and where each secret came from are printed.
"""

import argparse
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "deploy" / "env.full.example"
SERVICE = "mindgrid"
SECRET_NAMES = ("DB_OWNER_PASSWORD", "DB_APP_PASSWORD", "MINDGRID_SECRET_KEY")
MOCK_TAG = "[mock: replace]"
LINE = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")
# Every secret must survive each place it is used: a URL userinfo (DB_APP_PASSWORD in
# MINDGRID_DATABASE_URL: RFC 3986 unreserved characters only), compose interpolation (no
# "$"), `security -i` argument parsing (no leading "-", no spaces) and the 32-byte minimum
# of MINDGRID_SECRET_KEY. token_urlsafe(48) gives 64 such characters.
SECRET_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]{42,}$")
URL_PATTERN = re.compile(
    r"^https://[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+(:\d+)?$"
)
# Fixed command names; the tools come from PATH.
SECURITY, PBCOPY = "security", "pbcopy"


def template_entries() -> list[tuple[str, str, bool]]:
    """(name, value, is_mock) for every active line of the generated template."""
    out: list[tuple[str, str, bool]] = []
    mock = False
    for raw in TEMPLATE.read_text(encoding="utf-8").splitlines():
        if raw.startswith("#"):
            mock = MOCK_TAG in raw
            continue
        match = LINE.match(raw)
        if match:
            out.append((match.group(1), match.group(2), mock))
            mock = False
    return out


def keychain_get(account: str) -> str | None:
    found = subprocess.run(  # noqa: S603 — fixed command, no shell
        [SECURITY, "find-generic-password", "-s", SERVICE, "-a", account, "-w"],
        capture_output=True,
        text=True,
        check=False,
    )
    return found.stdout.rstrip("\n") if found.returncode == 0 else None


def keychain_put(account: str, value: str) -> None:
    """Through `security -i` on stdin, so the value never appears in argv or `ps`."""
    command = f"add-generic-password -U -s {SERVICE} -a {account} -w {value}\n"
    done = subprocess.run(  # noqa: S603 — fixed command, no shell
        [SECURITY, "-i"], input=command, capture_output=True, text=True, check=False
    )
    if done.returncode != 0 or keychain_get(account) != value:
        sys.exit(f"error: could not store {account} in the Keychain")


def secret_values(profile: str, rotate: bool) -> dict[str, tuple[str, str]]:
    """NAME -> (value, "kept" | "new")."""
    out: dict[str, tuple[str, str]] = {}
    for name in SECRET_NAMES:
        account = f"{profile}:{name}"
        stored = None if rotate else keychain_get(account)
        if stored:
            if not SECRET_PATTERN.match(stored):
                sys.exit(f"error: Keychain {account} does not fit the pattern; use --rotate")
            out[name] = (stored, "kept")
        else:
            value = secrets.token_urlsafe(48)
            while value.startswith("-"):  # `security -i` would read it as an option
                value = secrets.token_urlsafe(48)
            if not SECRET_PATTERN.match(value):  # cannot happen with token_urlsafe; checked anyway
                sys.exit(f"error: generated {name} does not fit the pattern")
            keychain_put(account, value)
            out[name] = (value, "new")
    return out


def build(args: argparse.Namespace) -> tuple[list[str], dict[str, str]]:
    overrides = dict(item.split("=", 1) for item in args.set)
    if args.public_url:
        overrides["MINDGRID_PUBLIC_URL"] = args.public_url.rstrip("/")
    stored = secret_values(args.profile, args.rotate)
    lines: list[str] = []
    report: dict[str, str] = {}
    for name, default, mock in template_entries():
        value = default
        if name in stored:
            value, origin = stored[name]
            report[name] = f"{origin} secret ({len(value)} chars, Keychain {args.profile}:{name})"
        elif name in overrides:
            value = overrides.pop(name)
            report[name] = "set"
        elif mock:
            value = ""
            if name == "MINDGRID_PUBLIC_URL":
                report[name] = "MISSING: pass --public-url"
        if args.minimal and not value and name not in report:
            continue
        lines.append(f"{name}={value}")
    for name, value in overrides.items():  # names the template does not know yet
        lines.append(f"{name}={value}")
        report[name] = "set (not in the template)"
    return lines, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--public-url", help="Public https URL the engine is served at.")
    parser.add_argument("--profile", default="prod", help="Keychain account prefix.")
    parser.add_argument("--rotate", action="store_true", help="Make new secrets.")
    parser.add_argument("--set", action="append", default=[], metavar="NAME=VALUE")
    parser.add_argument("--minimal", action="store_true", help="Leave out blank lines.")
    parser.add_argument("--write", type=Path, help="Write to this file (0600) as well.")
    parser.add_argument("--no-copy", action="store_true", help="Do not use the clipboard.")
    args = parser.parse_args()
    if any("=" not in item for item in args.set):
        parser.error("--set takes NAME=VALUE")
    if args.public_url and not URL_PATTERN.match(args.public_url.rstrip("/").lower()):
        parser.error("--public-url must be https://<host>[:port] (no path)")
    lines, report = build(args)
    text = "\n".join(lines) + "\n"
    if args.write:
        descriptor = os.open(args.write, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        print(f"wrote {args.write} (0600)")
    if not args.no_copy:
        subprocess.run([PBCOPY], input=text, text=True, check=True)  # noqa: S603
        print("copied to the clipboard: paste it into the hosting panel's env editor")
    print(f"{len(lines)} variables")
    for name, note in report.items():
        print(f"  {name}: {note}")
    return 1 if any(n.startswith("MISSING") for n in report.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
