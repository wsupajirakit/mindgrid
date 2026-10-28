"""The function contract. A function takes one validated arguments model and returns one
output model; it reads nothing else (no database, no clock, no environment), so the same
arguments always give the same result and runs can be replayed."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic_core import CoreSchema, core_schema

from mindgrid.datasets import formats

Row = dict[str, Any]
Table = list[Row]


class Frame:
    """A pinned dataset version given to a function: its original bytes (so a pack can read
    them with its own parser, exactly), its metadata, and columns parsed on first use."""

    __slots__ = ("_columns", "media_type", "meta", "name", "raw", "records_path", "version")

    def __init__(  # noqa: PLR0913 - one value per attribute of a pinned version
        self,
        name: str,
        version: int,
        raw: bytes,
        media_type: str,
        meta: dict[str, Any],
        *,
        records_path: str = "",
    ) -> None:
        self.name, self.version, self.raw = name, version, raw
        self.media_type, self.meta, self.records_path = media_type, meta, records_path
        self._columns: dict[str, list[Any]] | None = None

    @property
    def columns(self) -> dict[str, list[Any]]:
        if self._columns is None:
            parsed = formats.parse(self.raw, self.media_type, self.records_path)
            self._columns = {c: [r.get(c) for r in parsed.rows] for c in parsed.columns}
        return self._columns

    @property
    def rows(self) -> int:
        return max((len(v) for v in self.columns.values()), default=0)

    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        del source, handler
        return core_schema.is_instance_schema(cls)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> dict[str, Any]:
        del schema, handler
        return {
            "type": "object",
            "title": "Frame",
            "description": "A dataset input, supplied by the runtime from a pinned version.",
        }

    def records(self, columns: list[str] | None = None, limit: int | None = None) -> list[Row]:
        data = self.columns
        names = [c for c in (columns or list(data)) if c in data]
        count = self.rows if limit is None else min(limit, self.rows)
        return [{c: data[c][i] for c in names} for i in range(count)]


class Args(BaseModel):
    """Base for function arguments: unknown fields are refused (typos fail loudly)."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)


class Output(BaseModel):
    model_config = ConfigDict(frozen=True)


@dataclass(frozen=True, slots=True)
class Function:
    id: str  # "<pack>.<group>.<name>", e.g. "core.table.filter"
    version: int
    summary: str
    args: type[Args]
    output: type[Output]
    run: Callable[[Any], Output]

    def call(self, raw: dict[str, Any]) -> Output:
        return self.run(self.args.model_validate(raw))

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "summary": self.summary,
            "args": self.args.model_json_schema(),
            "output": self.output.model_json_schema(),
        }
