#!/usr/bin/env python3
"""Fail when the default displayed name is written anywhere but its one config.

The name is read from mindgrid/core/brand.py (the MINDGRID_BRAND_NAME default), never
typed here. Everything that shows the name must read the brand config, and translations
must use a `{brand}` placeholder. Planning docs (docs/, README.md) may mention it.
Run: python3 tools/check_brand.py
"""

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRAND_FILE = ROOT / "backend" / "src" / "mindgrid" / "core" / "brand.py"
# Planning docs, the config itself, and files generated from it (the OpenAPI title, the
# full env reference with the default name).
ALLOWED = (
    "docs/",
    "README.md",
    BRAND_FILE.relative_to(ROOT).as_posix(),
    "deploy/env.full.example",
    "web/openapi/openapi.json",
    "web/src/services/api/openapi.gen.ts",
)
ENV_NAME = "MINDGRID_BRAND_NAME"


def default_name() -> str:
    tree = ast.parse(BRAND_FILE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and len(node.args) >= 2):
            continue
        first, second = node.args[0], node.args[1]
        names_env = isinstance(first, ast.Constant) and first.value == ENV_NAME
        if names_env and isinstance(second, ast.Constant) and isinstance(second.value, str):
            return second.value
    raise SystemExit(f"check_brand: {ENV_NAME} default not found in {BRAND_FILE.name}")


def project_files() -> list[Path]:
    git = ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"]
    result = subprocess.run(git, cwd=ROOT, capture_output=True, check=True)  # noqa: S603
    return [ROOT / name for name in result.stdout.decode().split("\0") if name]


def main() -> int:
    name = default_name()
    problems = 0
    for path in project_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(ALLOWED) or not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(lines, 1):
            if name in line:
                problems += 1
                print(f"{rel}:{number}: displayed name written directly; read the brand config")
    print(f"check_brand: {problems} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
