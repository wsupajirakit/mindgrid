"""The reranker interface. Scores are relevance probabilities in 0..1 (higher = closer),
so one cutoff works whatever model produced them."""

import math
from typing import Protocol


class Reranker(Protocol):
    @property
    def name(self) -> str: ...

    async def score(self, query: str, passages: list[str]) -> list[float]: ...


def probability(logit: float) -> float:
    """A cross-encoder logit as a probability (numerically safe both ways)."""
    if logit >= 0:
        return 1.0 / (1.0 + math.exp(-logit))
    z = math.exp(logit)
    return z / (1.0 + z)
