"""The writer interface."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Prompt:
    system: str
    user: str


class Writer(Protocol):
    @property
    def name(self) -> str: ...  # provider:model, recorded with every answer

    @property
    def max_prompt_chars(self) -> int | None: ...  # None = no practical limit

    async def write(self, prompt: Prompt) -> str: ...


class WriterError(RuntimeError):
    """The model could not produce an answer (unreachable, refused, empty)."""
