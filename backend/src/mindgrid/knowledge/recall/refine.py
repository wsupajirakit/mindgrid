"""Second stage: re-score the fused candidates with a cross-encoder and drop unrelated
ones. Without a reranker (switched off or failing), a passage needs an exact keyword match
or a cosine distance within the embedding model's measured limit, so an off-topic question
returns nothing rather than the least-bad passages (fuzzy trigram matches on common words
alone do not count)."""

import dataclasses

import structlog

from mindgrid.providers import config as provider_config
from mindgrid.providers.rerank import factory as rerank_factory

from . import config as recall_config
from .types import Hit, Recall

log = structlog.get_logger(__name__)


def _by_distance(hits: list[Hit], limit: float) -> list[Hit]:
    def kept(h: Hit) -> bool:
        exact_words = "keyword" in h.ranks
        return exact_words or (h.distance is not None and h.distance <= limit)

    return [h for h in hits if kept(h)]


def _distance_limit() -> float:
    configured = recall_config.get_settings().max_vector_distance
    return configured or provider_config.get_settings().off_topic_distance()


async def _reranked(query: str, hits: list[Hit], out: Recall) -> list[Hit] | None:
    try:
        reranker = rerank_factory.build()
    except Exception as err:  # misconfigured: fall back to the distance cutoff
        out.skipped["rerank"] = f"reranker unavailable: {type(err).__name__}"
        return None
    if reranker is None:
        out.skipped["rerank"] = "reranking is switched off"
        return None
    texts = [f"{h.heading}\n{h.text}" if h.heading else h.text for h in hits]
    try:
        scores = await reranker.score(query, texts)
    except Exception as err:  # model load or runtime failure: degrade, do not fail
        log.warning("recall.rerank_failed", error=repr(err))
        out.skipped["rerank"] = "reranking failed"
        return None
    out.reranker = reranker.name
    scored = [
        dataclasses.replace(h, relevance=round(s, 6)) for h, s in zip(hits, scores, strict=True)
    ]
    return sorted(scored, key=lambda h: -(h.relevance or 0.0))


async def refine(query: str, candidates: list[Hit], k: int, out: Recall) -> list[Hit]:
    cfg = recall_config.get_settings()
    reranked = await _reranked(query, candidates, out) if candidates else []
    if reranked is None:
        # Without a vector search (nothing indexed yet) meaning cannot be judged: keep the
        # word matches rather than return nothing.
        meaning_known = "vector" not in out.skipped
        kept = _by_distance(candidates, _distance_limit()) if meaning_known else candidates
    else:
        kept = [h for h in reranked if (h.relevance or 0.0) >= cfg.min_relevance]
    out.dropped = len(candidates) - len(kept)
    return kept[:k]
