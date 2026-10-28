#!/usr/bin/env python3
"""Fail when a code note (comment or docstring) is not plain English engineering text.

Two rules, for every source file the project owns:
  language   notes are English only: no Thai characters in comments or docstrings
             (runtime strings shown to people are not notes and are not checked here)
  narrative  notes state the rule or the reason, never who requested a change or what
             anyone holds (the NARRATIVE pattern below lists the phrasings)

Exempt: generated and vendored files.
Run: python3 tools/check_notes.py
"""

import ast
import io
import re
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THAI = re.compile(r"[฀-๿]")
# Narrative = a person followed by a request verb, or "per <person>" (_WHO, _ASKED).
# Technical uses of the same nouns (owner role, user row, user agent) do not match.
_WHO = r"(?:the )?(?:user|owner|client|boss)(?:'s)?"
_ASKED = r"(?:decided|decision|asked|said|wants|wanted|chose|requested|confirmed|ordered)"
_PER = r"\bper (?:the )?(?:user|owner)\b(?! gesture| activation| agent)"
NARRATIVE = re.compile(rf"(?i)\b{_WHO} {_ASKED}\b|{_PER}|\brequested by\b")
SKIP_PARTS = ("node_modules", ".venv", "__pycache__", "dist", "paraglide", "golden", "fixtures")
SKIP_PATHS = ("web/src/app/routeTree.gen.ts", "web/src/services/api/openapi.gen.ts")
HASH_COMMENTS = {".sh", ".toml", ".yml", ".yaml", ".cfg"}
SLASH_COMMENTS = {".ts", ".tsx", ".js", ".mjs", ".css"}
EXTRA_FILES = {"Dockerfile", ".githooks/pre-push"}


def _owned_files() -> list[Path]:
    out = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT).as_posix()
        if not path.is_file() or rel.startswith(SKIP_PATHS):
            continue
        if any(part in SKIP_PARTS for part in path.relative_to(ROOT).parts):
            continue
        known = path.suffix in HASH_COMMENTS | SLASH_COMMENTS | {".py"}
        if known or rel in EXTRA_FILES:
            out.append(path)
    return sorted(out)


def _python_notes(source: str) -> list[tuple[int, str]]:
    notes = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                notes.append((tok.start[0], tok.string))
        tree = ast.parse(source)
    except tokenize.TokenError, SyntaxError:
        return notes
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                first = node.body[0].lineno
                notes += [(first + i, line) for i, line in enumerate(doc.splitlines())]
    return notes


def _text_notes(source: str, hash_style: bool) -> list[tuple[int, str]]:
    pattern = re.compile(r"(?m)#[^\n]*$" if hash_style else r"//[^\n]*|/\*.*?\*/", re.S)
    notes = []
    for match in pattern.finditer(source):
        first = source.count("\n", 0, match.start()) + 1
        notes += [(first + i, line) for i, line in enumerate(match.group(0).splitlines())]
    return notes


def check(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix == ".py":
        notes = _python_notes(source)
    else:
        notes = _text_notes(source, path.suffix in HASH_COMMENTS or path.suffix == "")
    rel = path.relative_to(ROOT).as_posix()
    problems = []
    for line, text in notes:
        if THAI.search(text):
            problems.append(f"{rel}:{line}: non-English note: {text.strip()[:80]}")
        elif NARRATIVE.search(text):
            problems.append(f"{rel}:{line}: narrative note: {text.strip()[:80]}")
    return problems


def main() -> int:
    problems = [p for f in _owned_files() for p in check(f)]
    for p in problems:
        print(p)
    print(f"check_notes: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
