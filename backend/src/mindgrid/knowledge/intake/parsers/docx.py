"""Word (.docx): paragraphs and tables in document order, one section per heading with the
heading path ("A > B") kept as context, like Markdown. Read with the standard library
(the file is a zip of XML parts); the main part is size-capped against zip bombs, and a
part with a document type declaration is refused (Word never writes one), which rules out
entity expansion and external entities.

A heading is a paragraph whose style is a heading style ("Heading1", "Title", ...) or that
carries an outline level, so documents written in localised Word versions work too. A file
with no such paragraph at all (exports that format headings by hand, e.g. Pages) falls
back to the look: a short paragraph set larger than the body text is a heading, its level
given by the size (largest = 1)."""

import io
import re
import zipfile
from collections import Counter
from dataclasses import dataclass
from xml.etree import ElementTree

from mindgrid.core.errors import ApiError

from .. import config as intake_config
from ..sanitize import clean
from ..sections import Section

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MAIN_PART = "word/document.xml"
MAX_EXPANSION = 20  # the main XML part may be at most this many times the upload limit
MAX_LOOK_HEADING_CHARS = 150  # longer text set large is emphasis, not a heading
_HEADING_STYLE = re.compile(r"^(?:heading|berschrift|titre|titolo)\s*(\d)$", re.IGNORECASE)


def _unreadable() -> ApiError:
    return ApiError(400, "document.unreadable", "the Word file cannot be read")


def _main_xml(data: bytes) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            info = archive.getinfo(MAIN_PART)
            limit = intake_config.get_settings().max_upload_bytes * MAX_EXPANSION
            if info.file_size > limit:
                raise ApiError(413, "document.too_large", "the Word file expands too far")
            with archive.open(info) as part:
                return part.read(limit + 1)[:limit]
    except zipfile.BadZipFile, KeyError, OSError:
        raise _unreadable() from None


def _level(paragraph: ElementTree.Element) -> int:
    """Heading level 1-9, or 0 for body text."""
    props = paragraph.find(f"{W}pPr")
    if props is None:
        return 0
    style = props.find(f"{W}pStyle")
    name = style.get(f"{W}val", "") if style is not None else ""
    if name.lower() == "title":
        return 1
    match = _HEADING_STYLE.match(name)
    if match:
        return max(int(match.group(1)), 1)
    outline = props.find(f"{W}outlineLvl")
    if outline is not None and outline.get(f"{W}val", "").isdigit():
        return min(int(outline.get(f"{W}val", "0")) + 1, 9)
    return 0


def _text(element: ElementTree.Element) -> str:
    out: list[str] = []
    for node in element.iter():
        if node.tag == f"{W}t" and node.text:
            out.append(node.text)
        elif node.tag == f"{W}tab":
            out.append("\t")
        elif node.tag in (f"{W}br", f"{W}cr"):
            out.append("\n")
    return "".join(out)


def _table(table: ElementTree.Element) -> str:
    rows: list[str] = []
    for row in table.iter(f"{W}tr"):
        cells = [" ".join(_text(c).split()) for c in row.findall(f"{W}tc")]
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


@dataclass(frozen=True, slots=True)
class _Block:
    number: int
    text: str
    level: int  # from the style or outline level; 0 = body text
    size: int  # largest font size in half-points (0 = not set)
    table: bool = False


def _size(paragraph: ElementTree.Element) -> int:
    sizes = [int(v) for n in paragraph.iter(f"{W}sz") if (v := n.get(f"{W}val", "")).isdigit()]
    return max(sizes, default=0)


def _blocks(body: ElementTree.Element) -> list[_Block]:
    out: list[_Block] = []
    for number, block in enumerate(body, start=1):
        if block.tag == f"{W}tbl":
            out.append(_Block(number, _table(block), 0, 0, table=True))
        elif block.tag == f"{W}p":
            out.append(_Block(number, _text(block), _level(block), _size(block)))
    return out


def _levels_by_look(blocks: list[_Block]) -> list[_Block]:
    """No styled heading anywhere: short paragraphs larger than the body become headings."""
    weight = Counter[int]()
    for b in blocks:
        if not b.table and b.size:
            weight[b.size] += len(b.text)
    if not weight:
        return blocks
    body = weight.most_common(1)[0][0]

    def heading(b: _Block) -> bool:
        short = 0 < len(b.text.strip()) <= MAX_LOOK_HEADING_CHARS
        return not b.table and short and b.size > body

    sizes = sorted({b.size for b in blocks if heading(b)}, reverse=True)
    rank = {size: i for i, size in enumerate(sizes[:9], start=1)}
    return [
        _Block(b.number, b.text, rank.get(b.size, 0), b.size) if heading(b) else b for b in blocks
    ]


def parse(data: bytes) -> list[Section]:
    xml = _main_xml(data)
    if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
        raise _unreadable()
    try:
        root = ElementTree.fromstring(xml)  # noqa: S314 — no DTD, so no entity tricks
    except ElementTree.ParseError:
        raise _unreadable() from None
    body = root.find(f"{W}body")
    if body is None:
        raise _unreadable()
    blocks = _blocks(body)
    if not any(b.level for b in blocks):
        blocks = _levels_by_look(blocks)
    sections: list[Section] = []
    path: list[str] = []
    lines: list[str] = []
    start = 1

    def flush(next_start: int) -> None:
        nonlocal start
        text = clean("\n".join(lines))
        if text:
            sections.append(Section(text, " > ".join(path), {"paragraph": start}))
        lines.clear()
        start = next_start

    for b in blocks:
        if b.level and b.text.strip():
            flush(b.number + 1)
            path[b.level - 1 :] = [clean(b.text)]
        else:
            lines.append(b.text)
    flush(0)
    return sections
