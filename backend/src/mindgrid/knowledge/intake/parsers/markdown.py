"""Markdown: one section per heading, with the heading path ("A > B") kept as context."""

import re

from ..sanitize import clean
from ..sections import Section
from .text_decode import decode

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def parse(data: bytes) -> list[Section]:
    sections: list[Section] = []
    path: list[str] = []
    lines: list[str] = []

    def flush() -> None:
        text = clean("\n".join(lines))
        if text:
            sections.append(Section(text=text, heading=" > ".join(path)))
        lines.clear()

    for line in decode(data).splitlines():
        match = _HEADING.match(line)
        if match is None:
            lines.append(line)
            continue
        flush()
        level = len(match.group(1))
        path[level - 1 :] = [clean(match.group(2))]
    flush()
    return sections
