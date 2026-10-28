"""Every error code the API can raise has a translated message in the web (all locales)."""

import ast
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "backend" / "src" / "mindgrid"
WEB_MAP = REPO / "web" / "src" / "services" / "api" / "errorMessages.ts"
LOCALES = ("en", "th", "it")


def _code_of(node: ast.AST) -> str | None:
    """The literal code of an `ApiError(status, "code", ...)` call, else None."""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
        return None
    if node.func.id != "ApiError" or len(node.args) < 2:
        return None
    code = node.args[1]
    return code.value if isinstance(code, ast.Constant) and isinstance(code.value, str) else None


def _raised_codes() -> set[str]:
    codes: set[str] = set()
    for path in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            code = _code_of(node)
            if code is not None:
                codes.add(code)
    return codes


def test_every_api_error_code_is_translated() -> None:
    mapped = set(re.findall(r"^\s*'([a-z0-9_.]+)':", WEB_MAP.read_text(encoding="utf-8"), re.M))
    missing = _raised_codes() - mapped
    assert not missing, f"add to web/src/services/api/errorMessages.ts: {sorted(missing)}"
    for locale in LOCALES:
        messages = json.loads((REPO / "web" / "messages" / f"{locale}.json").read_text("utf-8"))
        absent = [c for c in mapped if f"err_{c.replace('.', '_')}" not in messages]
        assert not absent, f"{locale}.json lacks messages for {absent}"
