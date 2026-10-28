"""Recall request and result types (shared by the retrieval and refinement steps)."""

import uuid
from dataclasses import dataclass, field
from typing import Any

from ..library.models import Trust


@dataclass(frozen=True, slots=True)
class Ask:
    project_id: uuid.UUID
    query: str
    category_ids: tuple[uuid.UUID, ...] = ()
    k: int = 0  # 0 = the configured default


@dataclass(frozen=True, slots=True)
class Hit:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    category_id: uuid.UUID
    title: str
    trust: Trust
    heading: str
    text: str
    location: dict[str, Any]
    score: float  # fused (reciprocal rank) score
    ranks: dict[str, int]  # retriever -> 1-based rank (absent = not found by it)
    distance: float | None = None  # cosine distance, when found by meaning
    relevance: float | None = None  # reranker probability 0..1, when reranked


@dataclass(slots=True)
class Recall:
    hits: list[Hit] = field(default_factory=list[Hit])
    skipped: dict[str, str] = field(default_factory=dict[str, str])  # step -> reason
    space: str = ""
    reranker: str = ""
    dropped: int = 0  # candidates removed as unrelated by the cutoff
    rewritten: str = ""  # the extra search query from recall.rewrite, when used
