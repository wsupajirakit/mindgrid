"""Hybrid recall: run the retrievers, fuse their rankings with reciprocal rank fusion
(score = sum of 1 / (k + rank)), rerank and cut off unrelated candidates (refine.py), and
return the passages with where each came from.
A retriever that cannot run (no vectors yet, provider unavailable) is skipped and named
in `skipped`, so a caller always learns how complete the answer is."""

import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.platform.tenancy import access
from mindgrid.platform.tenancy.models import Level
from mindgrid.providers.embeddings.factory import ProviderUnavailableError

from ..index import service as indexing
from ..library.models import Chunk, Document
from . import config as recall_config
from . import refine, rewrite, search
from .types import Ask, Hit, Recall

__all__ = ["Ask", "Hit", "Recall", "fuse", "recall"]

log = structlog.get_logger(__name__)
RETRIEVERS = ("vector", "keyword", "trigram")


def fuse(rankings: dict[str, list[uuid.UUID]], rrf_k: int) -> list[tuple[uuid.UUID, float]]:
    scores: dict[uuid.UUID, float] = {}
    for ranked in rankings.values():
        for rank, chunk_id in enumerate(ranked, 1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], str(item[0])))


def _check(ask: Ask) -> tuple[str, int]:
    cfg = recall_config.get_settings()
    query = " ".join(ask.query.split())
    if not query:
        raise ApiError(400, "recall.empty_query", "the query is empty")
    if len(query) > cfg.max_query_chars:
        raise ApiError(
            400, "recall.query_too_long", "query too long", params={"max": cfg.max_query_chars}
        )
    return query, min(ask.k or cfg.default_k, cfg.max_k)


async def _scope(tx: AsyncSession, ask: Ask) -> search.Scope:
    await access.require_project_view(tx, ask.project_id)
    for category_id in ask.category_ids:
        await access.require_category(tx, category_id, Level.READ)
        if await access.project_of_category(tx, category_id) != ask.project_id:
            raise ApiError(404, "category.not_found", "category not found")
    return search.Scope(ask.project_id, tuple(dict.fromkeys(ask.category_ids)))


async def _vector(
    tx: AsyncSession, scope: search.Scope, query: str, out: Recall
) -> list[tuple[uuid.UUID, float]]:
    try:
        embedder = await indexing.embedder_for(tx, scope.project_id)
    except ProviderUnavailableError as err:  # not configured: keyword search still answers
        out.skipped["vector"] = f"provider unavailable: {err}"
        return []
    out.space = embedder.space.key
    if not await search.has_vectors(tx, scope, embedder.space):
        out.skipped["vector"] = "nothing indexed in this embedding space yet"
        return []
    try:
        vector = await embedder.embed_query(query)
    except Exception as err:  # model or network failure: degrade, do not fail the request
        log.warning("recall.embed_failed", error=repr(err))
        out.skipped["vector"] = "embedding the query failed"
        return []
    return await search.by_vector(tx, scope, embedder.space, vector)


@dataclass(frozen=True, slots=True)
class _Ranked:
    fused: list[tuple[uuid.UUID, float]]
    rankings: dict[str, list[uuid.UUID]]
    distances: dict[uuid.UUID, float]


async def _hydrate(tx: AsyncSession, ranked: _Ranked) -> list[Hit]:
    ids = [chunk_id for chunk_id, _ in ranked.fused]
    query = (
        select(Chunk, Document.title, Document.trust)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.id.in_(ids))
    )
    found = {row[0].id: row for row in (await tx.execute(query)).all()}
    positions = {n: {cid: i for i, cid in enumerate(r, 1)} for n, r in ranked.rankings.items()}
    hits: list[Hit] = []
    for chunk_id, score in ranked.fused:
        if chunk_id not in found:
            continue
        chunk, title, trust = found[chunk_id]
        hits.append(
            Hit(
                chunk.id,
                chunk.document_id,
                chunk.category_id,
                title,
                trust,
                chunk.heading,
                chunk.text,
                dict(chunk.location),
                round(score, 6),
                {n: p[chunk_id] for n, p in positions.items() if chunk_id in p},
                distance=ranked.distances.get(chunk_id),
            )
        )
    return hits


async def recall(tx: AsyncSession, ask: Ask) -> Recall:
    query, k = _check(ask)
    scope = await _scope(tx, ask)
    cfg = recall_config.get_settings()
    out = Recall()
    near = await _vector(tx, scope, query, out)
    rankings = {
        "vector": [chunk_id for chunk_id, _ in near],
        "keyword": await search.by_keyword(tx, scope, query),
        "trigram": await search.by_trigram(tx, scope, query),
    }
    distances = dict(near)
    extra = await rewrite.rewritten(tx, ask, query, out)
    if extra:
        more = await _vector(tx, scope, extra, Recall())
        rankings["vector_rewrite"] = [chunk_id for chunk_id, _ in more]
        rankings["keyword_rewrite"] = await search.by_keyword(tx, scope, extra)
        for chunk_id, distance in more:
            distances[chunk_id] = min(distance, distances.get(chunk_id, distance))
    pool = max(cfg.rerank_candidates, k)
    ranked = _Ranked(fuse(rankings, cfg.rrf_k)[:pool], rankings, distances)
    out.hits = await refine.refine(query, await _hydrate(tx, ranked), k, out)
    return out
