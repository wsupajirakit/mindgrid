"""Deterministic bag-of-words vectors for tests (no model download). Similar wording gives
similar vectors, which is enough to test the pipeline; never used for real retrieval."""

import hashlib
import re

from .base import Space, normalize

_WORD = re.compile(r"\w+", re.UNICODE)


class HashingEmbedder:
    def __init__(self, dims: int = 64) -> None:
        self._space = Space("hashing", "bag-of-words", dims)

    @property
    def space(self) -> Space:
        return self._space

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self._space.dims
        for word in _WORD.findall(text.lower()):
            slot = int.from_bytes(hashlib.sha256(word.encode()).digest()[:4], "big")
            vector[slot % self._space.dims] += 1.0
        return normalize(vector)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._vector(text)
