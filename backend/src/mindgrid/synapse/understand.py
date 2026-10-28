"""Turn changed files into proposal items with mapping rules (data, per source):
`{"glob": "**/SKILL.md", "kind": "rules"}` ... The first matching rule wins; `exclude`
drops a file before anything is read. Kinds: rules / evidence / docs become knowledge
updates, code becomes a code task (with the functions its hunks touch), and numeric claims
in added lines become measurement items (to be re-measured on the engine's own data)."""

import fnmatch
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

KNOWLEDGE_KINDS = {"rules", "evidence", "docs"}
_HUNK_FN = re.compile(r"^@@ .*?@@\s*(?:async\s+)?(?:def|class|function)\s+([A-Za-z_][\w]*)", re.M)
_RESULT_WORDS = (
    r"win|wins|won|hit|edge|returns?|cagr|sharpe|drawdown|accuracy|precision|median|"
    r"mean|average|avg|beat|beats|outperform\w*|expectancy|ชนะ|กำไรเฉลี่ย"
)
# A measured-result claim: a percentage (or ratio like 14/14) next to a result word.
_CLAIM = re.compile(
    rf"[^.\n]{{0,50}}\b(?:{_RESULT_WORDS})\b[^.\n]{{0,40}}?(?:[-+]?\d+(?:\.\d+)?\s?%|\b\d+/\d+\b)"
    rf"[^.\n]{{0,30}}|[^.\n]{{0,30}}(?:[-+]?\d+(?:\.\d+)?\s?%)[^.\n]{{0,20}}\b(?:{_RESULT_WORDS})\b"
    rf"[^.\n]{{0,30}}",
    re.I,
)
PER_FILE_CLAIMS = 5


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    glob: str
    kind: str = Field(pattern=r"^(rules|evidence|docs|code|ignore)$")
    target: str = ""  # e.g. "pack:markets" for code rules


class Mapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    include: list[str] = Field(default_factory=lambda: ["**"])
    exclude: list[str] = Field(default_factory=list[str])
    rules: list[Rule] = Field(default_factory=list[Rule])
    redact: list[str] = Field(default_factory=list[str])  # extra patterns, replaced
    drop_lines: list[str] = Field(default_factory=list[str])  # whole lines removed

    @field_validator("redact", "drop_lines")
    @classmethod
    def _compiles(cls, patterns: list[str]) -> list[str]:
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error as err:
                raise ValueError(f"pattern {pattern!r} does not compile: {err}") from err
        return patterns


def _match(path: str, pattern: str) -> bool:
    return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, pattern.removeprefix("**/"))


def wanted(mapping: Mapping, path: str) -> bool:
    return any(_match(path, p) for p in mapping.include) and not any(
        _match(path, p) for p in mapping.exclude
    )


def rule_for(mapping: Mapping, path: str) -> Rule:
    return next((r for r in mapping.rules if _match(path, r.glob)), Rule(glob="**", kind="docs"))


def touched_functions(patch_text: str) -> list[str]:
    return sorted(set(_HUNK_FN.findall(patch_text)))


def claims(patch_text: str, limit: int = PER_FILE_CLAIMS) -> list[str]:
    """Measured-result claims in added lines of a patch (at most `limit` per file)."""
    found: list[str] = []
    for line in patch_text.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for m in _CLAIM.finditer(line[1:]):
            text = " ".join(m.group(0).split())
            if text and text not in found:
                found.append(text)
    return found[:limit]


@dataclass(slots=True)
class Item:
    kind: str  # knowledge_update | knowledge_remove | code_task | measure
    path: str
    summary: str
    detail: dict[str, Any] = field(default_factory=dict[str, Any])
    decision: str = "pending"  # pending | accepted | rejected

    def as_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "path": self.path,
            "summary": self.summary,
            "detail": self.detail,
            "decision": self.decision,
        }
