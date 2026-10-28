"""The embedder interface and its embedding space (provider + model + dimensions)."""

import math
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Space:
    provider: str
    model: str
    dims: int

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.model}@{self.dims}"


class Embedder(Protocol):
    @property
    def space(self) -> Space: ...

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


def normalize(vector: list[float]) -> list[float]:
    """Unit length, so cosine distance and inner product agree."""
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]
