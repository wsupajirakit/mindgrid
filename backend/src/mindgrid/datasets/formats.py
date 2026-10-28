"""Read a dataset file into rows. CSV: a UTF-8 BOM is ignored, leading `# key: value`
lines become metadata, numbers become numbers, empty cells become null. JSON: a list of
objects, or an object holding one at `records_path` (dot path); the value there may also be
column-oriented (one equal-length list per column, e.g. weather APIs), which becomes rows.
NDJSON: one object per line."""

import csv
import json
import re
from dataclasses import dataclass, field
from typing import Any, cast

_META = re.compile(r"^#\s*([A-Za-z0-9_.-]+)\s*:\s*(.*)$")
_INT = re.compile(r"^[+-]?\d+$")
_FLOAT = re.compile(r"^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$")
_BOOL = {"true": True, "false": False, "True": True, "False": False}


@dataclass(slots=True)
class Parsed:
    rows: list[dict[str, Any]]
    columns: list[str]
    meta: dict[str, str] = field(default_factory=dict[str, str])


class FormatError(ValueError):
    pass


def _value(cell: str) -> Any:
    if cell == "":
        return None
    if _INT.match(cell):
        return int(cell)
    if _FLOAT.match(cell):
        return float(cell)
    return _BOOL.get(cell, cell)


def _csv(text: str) -> Parsed:
    lines = text.splitlines()
    meta: dict[str, str] = {}
    start = 0
    while start < len(lines) and lines[start].startswith("#"):
        for part in lines[start].lstrip("#").split(" | "):  # "a: 1 | b: 2" holds two keys
            found = _META.match("#" + part.strip())
            if found:
                meta[found.group(1)] = found.group(2).strip()
        start += 1
    reader = csv.reader(lines[start:])
    no_header: list[str] = []
    header = next(reader, no_header)
    rows = [
        {h: _value(c) for h, c in zip(header, cells, strict=False)} for cells in reader if cells
    ]
    return Parsed(rows, header, meta)


def _columns_to_rows(table: dict[str, Any]) -> list[dict[str, Any]]:
    """{"time": [a, b], "temp": [1, 2]} -> [{"time": a, "temp": 1}, {"time": b, "temp": 2}]."""
    columns = {k: cast(list[Any], v) for k, v in table.items() if isinstance(v, list)}
    lengths = {len(v) for v in columns.values()}
    if not columns or len(lengths) != 1:
        raise FormatError("records must be a list of objects or equal-length column lists")
    names = list(columns)
    return [dict(zip(names, values, strict=True)) for values in zip(*columns.values(), strict=True)]


def _records(data: Any, records_path: str) -> list[dict[str, Any]]:
    for key in [k for k in records_path.split(".") if k]:
        if not isinstance(data, dict) or key not in data:
            raise FormatError(f"no records at {records_path!r}")
        data = cast(dict[str, Any], data)[key]
    if isinstance(data, dict):
        return _columns_to_rows(cast(dict[str, Any], data))
    if not isinstance(data, list) or not all(isinstance(r, dict) for r in cast(list[Any], data)):
        raise FormatError("records must be a list of objects")
    return cast(list[dict[str, Any]], data)


def parse(data: bytes, media_type: str, records_path: str = "") -> Parsed:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as err:
        raise FormatError("the file is not UTF-8 text") from err
    if media_type == "text/csv":
        return _csv(text)
    if media_type == "application/x-ndjson":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    elif media_type == "application/json":
        rows = _records(json.loads(text), records_path)
    else:
        raise FormatError(f"unsupported dataset format {media_type}")
    columns = list(dict.fromkeys(k for r in rows for k in r))
    return Parsed(rows, columns)
