#!/usr/bin/env python3
"""Fail when backend Python breaks the structure rules.

  file      <= 300 lines             function  <= 60 lines (decorators to last line)
  routes    an `async def` route must await something (blocking work belongs in `def`)
  config    no module reads os.environ / os.getenv: Settings classes do (core/config.py)
  layers    a package imports only the layers listed in LAYERS (one-way dependencies);
            packs/* import only mindgrid.core and mindgrid.functions
Run: python3 tools/check_structure.py
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SCAN = ("src", "tests", "packs")
MAX_FILE_LINES = 300
MAX_FUNCTION_LINES = 60
_ENV_READS = {"environ", "getenv", "getenvb"}
# Package -> the mindgrid packages it may import (itself always allowed).
LAYERS: dict[str, set[str]] = {
    "core": set(),
    "db": {"core"},
    "platform": {"core", "db"},
    "providers": {"core"},
    "datasets": {"core", "db", "platform"},
    "knowledge": {"core", "db", "platform", "providers"},
    "functions": {"core", "datasets"},
    "playbooks": {"core", "db", "platform", "functions", "datasets", "knowledge"},
    "runs": {
        "core",
        "db",
        "platform",
        "playbooks",
        "functions",
        "datasets",
        "knowledge",
        "providers",
    },
    "evals": {"core", "db", "platform", "knowledge", "providers", "runs"},
    "synapse": {"core", "db", "platform", "knowledge", "playbooks", "functions", "providers"},
    "bridges": {"core", "db", "platform", "datasets"},
    "insights": {"core", "db", "platform", "datasets", "knowledge", "playbooks", "runs"},
    "interfaces": {"*"},
    "app": {"*"},
}
PACK_ALLOWED = {"core", "functions"}


def _files() -> list[Path]:
    out = [p for d in SCAN if (BACKEND / d).exists() for p in (BACKEND / d).rglob("*.py")]
    return sorted(p for p in out if ".venv" not in p.parts)


def _owner(rel: str) -> str | None:
    parts = rel.split("/")
    if parts[:2] == ["src", "mindgrid"] and len(parts) > 2:
        return parts[2].removesuffix(".py")
    return None


def _imported_layers(tree: ast.AST) -> set[str]:
    found = set()
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module]
        for name in names:
            parts = name.split(".")
            if parts[0] == "mindgrid" and len(parts) > 1:
                found.add(parts[1])
    return found


def _layer_problems(rel: str, tree: ast.AST) -> list[str]:
    used = _imported_layers(tree)
    if rel.startswith("packs/"):
        bad = used - PACK_ALLOWED
        return [f"{rel}: packs may not import mindgrid.{b}" for b in sorted(bad)]
    owner = _owner(rel)
    if owner is None or owner == "__init__":
        return []
    allowed = LAYERS.get(owner)
    if allowed is None:
        return [f"{rel}: package '{owner}' has no entry in LAYERS"]
    if "*" in allowed:
        return []
    bad = used - allowed - {owner}
    return [f"{rel}: {owner} may not import mindgrid.{b}" for b in sorted(bad)]


def _reads_env(node: ast.AST) -> bool:
    if isinstance(node, ast.Attribute):
        owner = node.value
        return node.attr in _ENV_READS and isinstance(owner, ast.Name) and owner.id == "os"
    if isinstance(node, ast.ImportFrom) and node.module == "os":
        return any(alias.name in _ENV_READS for alias in node.names)
    return False


def _is_route(node: ast.AsyncFunctionDef) -> bool:
    return any("router." in ast.unparse(d) or "app." in ast.unparse(d) for d in node.decorator_list)


def _awaits(node: ast.AsyncFunctionDef) -> bool:
    return any(isinstance(n, ast.Await | ast.AsyncFor | ast.AsyncWith) for n in ast.walk(node))


def _node_problems(rel: str, node: ast.AST, app_code: bool) -> list[str]:
    out = []
    if app_code and _reads_env(node):
        out.append(f"{rel}:{node.lineno} reads the environment; use a Settings class")
    if isinstance(node, ast.AsyncFunctionDef) and _is_route(node) and not _awaits(node):
        out.append(f"{rel}:{node.lineno} async route {node.name}() never awaits")
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
        size = (node.end_lineno or node.lineno) - first + 1
        if size > MAX_FUNCTION_LINES:
            out.append(f"{rel}:{node.lineno} {node.name}() {size} lines > {MAX_FUNCTION_LINES}")
    return out


def check(path: Path) -> list[str]:
    rel = path.relative_to(BACKEND).as_posix()
    source = path.read_text(encoding="utf-8")
    problems = []
    lines = source.count("\n") + (0 if source.endswith("\n") else 1)
    if lines > MAX_FILE_LINES:
        problems.append(f"{rel}: {lines} lines > {MAX_FILE_LINES}")
    tree = ast.parse(source)
    app_code = rel.startswith(("src/", "packs/")) and "_tests/" not in rel
    for node in ast.walk(tree):
        problems += _node_problems(rel, node, app_code)
    return problems + _layer_problems(rel, tree)


def main() -> int:
    problems = [p for f in _files() for p in check(f)]
    for p in problems:
        print(p)
    print(f"check_structure: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
