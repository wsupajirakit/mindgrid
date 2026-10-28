"""Citation checks for an answer written from a Context Pack: every reference must exist
in the pack, and every substantive paragraph must cite at least one passage."""

import re
from dataclasses import dataclass, field

_GROUP = re.compile(r"\[\s*(P\d+(?:\s*,\s*P\d+)*)\s*\]")
_REF = re.compile(r"P\d+")
MIN_PARAGRAPH_CHARS = 40  # shorter lines (greetings, headings, "not found") need no source


@dataclass(frozen=True, slots=True)
class CitationCheck:
    cited: list[str] = field(default_factory=list[str])
    unknown: list[str] = field(default_factory=list[str])  # cited but not in the pack
    uncited: list[str] = field(default_factory=list[str])  # paragraphs without a source

    @property
    def ok(self) -> bool:
        return bool(self.cited) and not self.unknown and not self.uncited


def _paragraphs(answer: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n|\n(?=\s*[-*•]|\s*\d+\.)", answer) if p.strip()]


def verify(answer: str, refs: list[str]) -> CitationCheck:
    known = set(refs)
    cited: list[str] = []
    for group in _GROUP.findall(answer):
        cited += [r for r in _REF.findall(group) if r not in cited]
    uncited = [
        p[:120]
        for p in _paragraphs(answer)
        if len(p) >= MIN_PARAGRAPH_CHARS and not _GROUP.search(p)
    ]
    return CitationCheck(cited, [r for r in cited if r not in known], uncited)
