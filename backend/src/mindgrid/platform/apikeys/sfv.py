"""Typed adapter over http_sfv (RFC 8941 Structured Fields), which ships without complete
type hints: the rest of the code only sees these typed results."""

from dataclasses import dataclass
from typing import Any, cast

from http_sfv.dictionary import Dictionary


class FieldError(ValueError):
    """The header is not a well-formed structured field."""


@dataclass(frozen=True, slots=True)
class InnerList:
    items: tuple[str, ...]
    params: dict[str, object]


def _parse(value: str) -> Any:
    parsed: Any = Dictionary()
    try:
        parsed.parse(value.encode())
    except Exception as err:
        raise FieldError(str(err)) from err
    return parsed


def inner_list(value: str, label: str) -> tuple[InnerList, str]:
    """The inner list stored under `label`, and the dictionary re-serialised (canonical)."""
    parsed = _parse(value)
    if len(parsed) != 1 or label not in parsed:
        raise FieldError(f"exactly one member '{label}' is expected")
    member = parsed[label]
    items = tuple(str(item.value) for item in member)
    params = cast("dict[str, object]", dict(member.params))
    return InnerList(items, params), str(parsed).split("=", 1)[1]


def byte_sequence(value: str, label: str) -> bytes:
    parsed = _parse(value)
    if label not in parsed or not isinstance(parsed[label].value, bytes):
        raise FieldError(f"'{label}' must be a byte sequence")
    return cast("bytes", parsed[label].value)
