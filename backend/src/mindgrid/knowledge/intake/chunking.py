"""Recursive chunking: split on the strongest boundary that keeps chunks under the target
(paragraphs, then lines, then sentences, then words, then characters), then add a small
overlap so a fact cut at a boundary still appears whole in one chunk. Tables (CSV
sections) arrive pre-grouped and are never cut mid-row."""

import itertools
from dataclasses import dataclass, field
from typing import Any

from .sections import Section

_SEPARATORS = ("\n\n", "\n", ". ", "。", "? ", "! ", " ")


@dataclass(frozen=True, slots=True)
class Piece:
    text: str
    heading: str
    location: dict[str, Any] = field(default_factory=dict[str, Any])


def _split(text: str, limit: int, separators: tuple[str, ...]) -> list[str]:
    if len(text) <= limit:
        return [text]
    for i, sep in enumerate(separators):
        if sep not in text:
            continue
        parts: list[str] = []
        current = ""
        for part in text.split(sep):
            candidate = f"{current}{sep}{part}" if current else part
            if len(candidate) <= limit:
                current = candidate
                continue
            if current:
                parts.append(current)
            current = part
        parts.append(current)
        return [p for chunk in parts for p in _split(chunk, limit, separators[i + 1 :]) if p]
    return [text[i : i + limit] for i in range(0, len(text), limit)]  # no boundary at all


def _with_overlap(parts: list[str], overlap: int) -> list[str]:
    if overlap <= 0 or len(parts) < 2:
        return parts
    out = [parts[0]]
    for previous, part in itertools.pairwise(parts):
        tail = previous[-overlap:]
        cut = tail.find(" ")
        out.append((tail[cut + 1 :] if 0 <= cut < len(tail) - 1 else tail) + " " + part)
    return out


def chunk(sections: list[Section], limit: int, overlap: int) -> list[Piece]:
    pieces: list[Piece] = []
    for section in sections:
        if section.location.get("rows"):  # pre-grouped table rows: keep whole
            pieces.append(Piece(section.text, section.heading, section.location))
            continue
        parts = _with_overlap(_split(section.text, limit, _SEPARATORS), overlap)
        pieces += [Piece(p.strip(), section.heading, section.location) for p in parts if p.strip()]
    return pieces
