"""CSV as knowledge: rows rendered as "column: value" lines, grouped so a chunk never cuts
a row. Numeric questions over CSV belong to datasets (SQL/functions), not to this path."""

import csv
import io

from mindgrid.core.errors import ApiError

from .. import config as intake_config
from ..sanitize import clean
from ..sections import Section
from .text_decode import decode


def parse(data: bytes) -> list[Section]:
    reader = csv.reader(io.StringIO(decode(data)))
    header = next(reader, None)
    if not header:
        raise ApiError(400, "document.empty", "the file has no content")
    columns = [clean(h) or f"column_{i + 1}" for i, h in enumerate(header)]
    per_chunk = intake_config.get_settings().csv_rows_per_chunk
    sections: list[Section] = []
    block: list[str] = []
    first = 2  # spreadsheet row numbers: the header is row 1
    for number, row in enumerate(reader, start=2):
        block.append("; ".join(f"{c}: {clean(v)}" for c, v in zip(columns, row, strict=False)))
        if len(block) == per_chunk:
            sections.append(Section("\n".join(block), location={"rows": [first, number]}))
            block, first = [], number + 1
    if block:
        sections.append(
            Section("\n".join(block), location={"rows": [first, first + len(block) - 1]})
        )
    return sections
