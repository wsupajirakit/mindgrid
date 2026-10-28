"""What a parser produces: ordered sections with a heading path and a location."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Section:
    text: str
    heading: str = ""
    location: dict[str, Any] = field(default_factory=dict[str, Any])  # page, rows, ...
