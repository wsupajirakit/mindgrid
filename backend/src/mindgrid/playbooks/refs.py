"""`$` references in a spec: listing them (for checks) and resolving them (at run time)."""

from collections.abc import Iterator
from typing import Any, cast

ROOTS = ("inputs", "params", "steps")


class RefError(ValueError):
    pass


def _parts(ref: str) -> list[str]:
    parts = ref[1:].split(".")
    if parts[0] not in ROOTS or len(parts) < 2 or (parts[0] == "steps" and len(parts) < 3):
        raise RefError(f"bad reference {ref!r}")
    return parts


def walk(value: Any) -> Iterator[list[str]]:
    """Every reference inside a value, as path parts."""
    if isinstance(value, str) and value.startswith("$") and not value.startswith("$$"):
        yield _parts(value)
    elif isinstance(value, list):
        for item in cast(list[Any], value):
            yield from walk(item)
    elif isinstance(value, dict):
        for item in cast(dict[str, Any], value).values():
            yield from walk(item)


def _lookup(parts: list[str], scope: dict[str, Any]) -> Any:
    current: Any = scope[parts[0]]
    for key in parts[1:]:
        if not isinstance(current, dict) or key not in current:
            raise RefError(f"${'.'.join(parts)} is not available")
        current = cast(dict[str, Any], current)[key]
    return current


def resolve(value: Any, scope: dict[str, Any]) -> Any:
    if isinstance(value, str) and value.startswith("$$"):
        return value[1:]
    if isinstance(value, str) and value.startswith("$"):
        return _lookup(_parts(value), scope)
    if isinstance(value, list):
        return [resolve(v, scope) for v in cast(list[Any], value)]
    if isinstance(value, dict):
        return {k: resolve(v, scope) for k, v in cast(dict[str, Any], value).items()}
    return value
