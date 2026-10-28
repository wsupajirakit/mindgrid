"""Table functions: filter, sort, take the top rows, pick columns. Rows are JSON objects;
a missing or non-comparable value never matches a filter and sorts last."""

from typing import Any, Literal

from pydantic import Field

from ..contracts import Args, Frame, Output, Table
from ..registry import function

Op = Literal["eq", "ne", "gt", "ge", "lt", "le", "in", "not_in", "contains"]


class Condition(Args):
    column: str
    op: Op
    value: Any


class FilterArgs(Args):
    rows: Table
    where: list[Condition] = Field(default_factory=list[Condition])  # all must hold


class Rows(Output):
    rows: Table
    count: int


def _holds(row: dict[str, Any], c: Condition) -> bool:  # noqa: PLR0911 — one branch per op
    value = row.get(c.column)
    if value is None:
        return False
    try:
        match c.op:
            case "eq":
                return bool(value == c.value)
            case "ne":
                return bool(value != c.value)
            case "gt":
                return bool(value > c.value)
            case "ge":
                return bool(value >= c.value)
            case "lt":
                return bool(value < c.value)
            case "le":
                return bool(value <= c.value)
            case "in":
                return value in c.value
            case "not_in":
                return value not in c.value
            case "contains":
                return str(c.value).casefold() in str(value).casefold()
    except TypeError:
        return False


@function("core.table.filter", "Keep the rows that meet every condition.", FilterArgs, Rows)
def filter_rows(a: FilterArgs) -> Rows:
    kept = [r for r in a.rows if all(_holds(r, c) for c in a.where)]
    return Rows(rows=kept, count=len(kept))


class SortArgs(Args):
    rows: Table
    by: str
    descending: bool = True


@function("core.table.sort", "Order rows by one column (missing values last).", SortArgs, Rows)
def sort_rows(a: SortArgs) -> Rows:
    present = [r for r in a.rows if isinstance(r.get(a.by), int | float | str)]
    missing = [r for r in a.rows if r not in present]
    try:
        ordered = sorted(present, key=lambda r: r[a.by], reverse=a.descending)
    except TypeError:  # mixed text and numbers: compare as text
        ordered = sorted(present, key=lambda r: str(r[a.by]), reverse=a.descending)
    return Rows(rows=ordered + missing, count=len(a.rows))


class TopArgs(Args):
    rows: Table
    n: int = Field(10, ge=1, le=10_000)


@function("core.table.top", "The first n rows.", TopArgs, Rows)
def top_rows(a: TopArgs) -> Rows:
    return Rows(rows=a.rows[: a.n], count=min(len(a.rows), a.n))


class SelectArgs(Args):
    rows: Table
    columns: list[str] = Field(min_length=1)


@function("core.table.select", "Keep only these columns.", SelectArgs, Rows)
def select_columns(a: SelectArgs) -> Rows:
    kept = [{c: r.get(c) for c in a.columns} for r in a.rows]
    return Rows(rows=kept, count=len(kept))


class FromFrameArgs(Args):
    frame: Frame
    columns: list[str] = Field(default_factory=list[str])  # empty = every column
    limit: int | None = Field(None, ge=1, le=1_000_000)


@function("core.table.from_dataset", "A dataset input as table rows.", FromFrameArgs, Rows)
def from_dataset(a: FromFrameArgs) -> Rows:
    rows = a.frame.records(a.columns or None, a.limit)
    return Rows(rows=rows, count=len(rows))
