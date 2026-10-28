"""Declared runtime settings (changed in the UI, stored per scope) — the counterpart of
the environment config. Every key is declared once, next to the code that reads it, with
its type, default, the scopes it may be set at and a doc line; anything undeclared is
refused. The effective value is the most specific one: category > project > user or
system > default."""

import enum
from dataclasses import dataclass
from typing import Any

from pydantic import TypeAdapter

from mindgrid.core.errors import CODE_PATTERN


class Scope(enum.StrEnum):
    SYSTEM = "system"
    USER = "user"
    PROJECT = "project"
    CATEGORY = "category"


@dataclass(frozen=True, slots=True)
class Definition:
    key: str
    adapter: TypeAdapter[Any]
    default: Any
    scopes: frozenset[Scope]
    doc: str

    def validate(self, value: object) -> Any:
        return self.adapter.validate_python(value)


_REGISTRY: dict[str, Definition] = {}


def define(key: str, type_: Any, default: object, scopes: set[Scope], doc: str) -> Definition:
    if not CODE_PATTERN.fullmatch(key):
        raise ValueError(f"setting key must be dotted lowercase, got {key!r}")
    if key in _REGISTRY:
        raise ValueError(f"setting {key!r} is declared twice")
    adapter: TypeAdapter[Any] = TypeAdapter(type_)
    definition = Definition(key, adapter, adapter.validate_python(default), frozenset(scopes), doc)
    _REGISTRY[key] = definition
    return definition


def get(key: str) -> Definition | None:
    return _REGISTRY.get(key)


def all_definitions() -> list[Definition]:
    return sorted(_REGISTRY.values(), key=lambda d: d.key)
