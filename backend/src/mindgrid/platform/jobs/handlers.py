"""Job kinds and their handlers. Feature modules register theirs at import time; the
platform never imports them, so the dependency stays one-way."""

from collections.abc import Awaitable, Callable
from typing import Any

from mindgrid.db.session import Actor

Handler = Callable[[Actor, dict[str, Any]], Awaitable[None]]
Periodic = Callable[[], Awaitable[None]]
_HANDLERS: dict[str, Handler] = {}
_PERIODIC: dict[str, tuple[float, Periodic]] = {}


class PermanentJobError(Exception):
    """Retrying cannot help (bad payload, removed document): fail the job now."""


def register(kind: str, handler: Handler) -> None:
    if _HANDLERS.get(kind, handler) is not handler:
        raise ValueError(f"job kind {kind!r} already has a handler")
    _HANDLERS[kind] = handler


def kinds() -> list[str]:
    return sorted(_HANDLERS)


def get(kind: str) -> Handler | None:
    return _HANDLERS.get(kind)


def every(name: str, seconds: float, task: Periodic) -> None:
    """A maintenance task the worker runs about every `seconds` (e.g. purging old rows)."""
    _PERIODIC[name] = (seconds, task)


def periodic() -> dict[str, tuple[float, Periodic]]:
    return dict(_PERIODIC)
