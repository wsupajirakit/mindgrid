#!/usr/bin/env python3
"""Fail when a project file names this machine: its account name, hostname, home path or
the private folder names between the home directory and the checkout.

Nothing private is written here: every name is read from the running machine, so the
check works on any machine and the file itself never leaks. Paths in docs and code use
`~`-free placeholders instead (e.g. "$ZSERVICE_REPO/tools").
Run: python3 tools/check_private.py
"""

import getpass
import re
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Folder names too common to identify anyone; every other segment between the home
# directory and the checkout counts as private.
GENERIC_SEGMENTS = {"project", "projects", "src", "code", "dev", "work", "repos", "git", "github"}
MIN_NAME_LEN = 4  # shorter host names ("mac") are ordinary words in code (MACD, macro)


def private_terms() -> list[str]:
    home = Path.home()
    terms = {getpass.getuser(), str(home)}
    host = socket.gethostname().split(".")[0]
    if len(host) >= MIN_NAME_LEN:
        terms.add(host)
    try:
        between = ROOT.parent.relative_to(home).parts
    except ValueError:
        between = ()
    terms |= {seg for seg in between if seg.lower() not in GENERIC_SEGMENTS}
    return sorted(t for t in terms if t)


def tracked_files() -> list[Path]:
    # Tracked plus new (not ignored) files, so a leak is caught before its first commit.
    git = ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"]
    result = subprocess.run(git, cwd=ROOT, capture_output=True, check=True)  # noqa: S603
    out = result.stdout.decode()
    return [ROOT / name for name in out.split("\0") if name]


def main() -> int:
    terms = private_terms()
    pattern = re.compile("|".join(rf"(?<![\w-]){re.escape(t)}(?![\w-])" for t in terms), re.I)
    problems = 0
    for path in tracked_files():
        if not path.is_file() or path.stat().st_size > 5_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # binary
        for number, line in enumerate(text.splitlines(), 1):
            if pattern.search(line):
                problems += 1
                # Print where, never what: the match itself is the private value.
                print(f"{path.relative_to(ROOT).as_posix()}:{number}: names this machine")
    print(f"check_private: {problems} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
