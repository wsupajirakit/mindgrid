"""The event catalog: every type with its data model (published with JSON Schema at
/v1/events/types). Modules declare their types next to their code; data is validated
before an event is recorded, so receivers can rely on the published shape."""

import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

TYPE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


class EventData(BaseModel):
    """Base for event data: thin (identifiers, status, links), never whole results."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Links(BaseModel):
    api: str
    ui: str


@dataclass(frozen=True, slots=True)
class EventType:
    name: str
    summary: str
    data: type[EventData]


_TYPES: dict[str, EventType] = {}


def define(name: str, summary: str, data: type[EventData]) -> EventType:
    if not TYPE.fullmatch(name):
        raise ValueError(f"event type {name!r} must look like area.event")
    known = _TYPES.get(name)
    if known is not None and known.data is not data:
        raise ValueError(f"event type {name!r} is defined twice")
    _TYPES[name] = EventType(name, summary, data)
    return _TYPES[name]


def get(name: str) -> EventType | None:
    return _TYPES.get(name)


def catalog_types() -> list[EventType]:
    return list(_TYPES.values())


def catalog() -> list[dict[str, Any]]:
    return [
        {"type": t.name, "summary": t.summary, "data": t.data.model_json_schema()}
        for t in sorted(_TYPES.values(), key=lambda t: t.name)
    ]


class Ping(EventData):
    subscription_id: str
    message: str


PING = define("subscription.test", "Sent on request to check that a receiver works.", Ping)
