"""Parser registry: one module per format; `parse` picks by extension and content."""

from collections.abc import Callable
from pathlib import PurePosixPath

from mindgrid.core.errors import ApiError

from ..sections import Section
from . import csv_table, docx, markdown, pdf, plain

Parser = Callable[[bytes], list[Section]]

PARSERS: dict[str, tuple[str, Parser]] = {
    ".txt": ("text/plain", plain.parse),
    ".md": ("text/markdown", markdown.parse),
    ".markdown": ("text/markdown", markdown.parse),
    ".csv": ("text/csv", csv_table.parse),
    ".pdf": ("application/pdf", pdf.parse),
    ".docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        docx.parse,
    ),
}
# Formats recognised by their first bytes: a wrong extension is refused before parsing.
MAGIC = {".pdf": b"%PDF-", ".docx": b"PK\x03\x04"}


def media_type(filename: str) -> str:
    entry = PARSERS.get(PurePosixPath(filename).suffix.lower())
    if entry is None:
        raise ApiError(
            415,
            "document.unsupported",
            "unsupported file type",
            params={"allowed": sorted(PARSERS)},
        )
    return entry[0]


def parse(filename: str, data: bytes) -> list[Section]:
    media_type(filename)  # refuses unknown types
    suffix = PurePosixPath(filename).suffix.lower()
    magic = MAGIC.get(suffix)
    if magic is not None and not data.startswith(magic):
        raise ApiError(
            415, "document.unsupported", f"not a {suffix} file", params={"allowed": [suffix]}
        )
    return PARSERS[suffix][1](data)
