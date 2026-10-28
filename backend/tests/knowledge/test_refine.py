"""Second stage: reranker order and cutoff, and the distance cutoff when reranking is off
or fails."""

import uuid
from collections.abc import Callable

import pytest

from mindgrid.knowledge.library.models import Trust
from mindgrid.knowledge.recall import refine
from mindgrid.knowledge.recall.types import Hit, Recall
from mindgrid.providers.rerank import factory

pytestmark = pytest.mark.anyio


def _hit(text: str, ranks: dict[str, int], distance: float | None = None) -> Hit:
    return Hit(
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        "t",
        Trust.UNRATED,
        "",
        text,
        {},
        0.01,
        ranks,
        distance=distance,
    )


class FakeReranker:
    name = "fake:cross"

    def __init__(self, scores: dict[str, float], fail: bool = False) -> None:
        self.scores = scores
        self.fail = fail

    async def score(self, query: str, passages: list[str]) -> list[float]:
        del query
        if self.fail:
            raise RuntimeError("model missing")
        return [self.scores[p] for p in passages]


async def test_reranker_reorders_and_drops_unrelated(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeReranker({"rates": 0.9, "credit": 0.2, "cake": 0.001})
    monkeypatch.setattr(factory, "build", lambda: fake)
    hits = [
        _hit("credit", {"vector": 1}),
        _hit("cake", {"keyword": 1}),
        _hit("rates", {"vector": 2}),
    ]
    out = Recall()
    kept = await refine.refine("why did yields rise", hits, 5, out)
    assert [h.text for h in kept] == ["rates", "credit"]
    assert kept[0].relevance == 0.9
    assert (out.reranker, out.dropped, out.skipped) == ("fake:cross", 1, {})


async def test_off_or_failing_reranker_uses_distance_cutoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hits = [
        _hit("near", {"vector": 1}, 0.4),
        _hit("far", {"vector": 2}, 0.8),
        _hit("far but exact words", {"vector": 3, "keyword": 1}, 0.9),
    ]
    out = Recall()
    kept = await refine.refine("q", hits, 5, out)  # tests run with reranking off
    assert [h.text for h in kept] == ["near", "far but exact words"]
    assert "switched off" in out.skipped["rerank"]
    monkeypatch.setattr(factory, "build", lambda: FakeReranker({}, fail=True))
    out = Recall()
    assert len(await refine.refine("q", hits, 5, out)) == 2
    assert out.skipped["rerank"] == "reranking failed"


async def test_k_limits_after_the_cutoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(factory, "build", lambda: FakeReranker({"a": 0.5, "b": 0.4, "c": 0.3}))
    hits = [_hit(t, {"keyword": i}) for i, t in enumerate("abc", 1)]
    assert [h.text for h in await refine.refine("q", hits, 2, Recall())] == ["a", "b"]


async def test_fuzzy_match_alone_is_not_enough_without_reranker() -> None:
    hits = [
        _hit("common word, far in meaning", {"trigram": 1, "vector": 4}, 0.85),
        _hit("common word, never near", {"trigram": 2}),
        _hit("close", {"trigram": 3, "vector": 1}, 0.5),
    ]
    assert [h.text for h in await refine.refine("q", hits, 5, Recall())] == ["close"]


async def test_distance_limit_follows_the_embedding_model(env: Callable[..., None]) -> None:
    hit = [_hit("between", {"vector": 1}, 0.65)]
    env(
        MINDGRID_EMBEDDING_PROVIDER="local", MINDGRID_EMBED_LOCAL_MODEL="google/embeddinggemma-300m"
    )
    assert len(await refine.refine("q", hit, 5, Recall())) == 1  # Gemma: 0.71
    env(MINDGRID_EMBED_LOCAL_MODEL="Qwen/Qwen3-Embedding-0.6B")
    assert await refine.refine("q", hit, 5, Recall()) == []  # Qwen: 0.6
    env(MINDGRID_RECALL_MAX_VECTOR_DISTANCE="0.7")
    assert len(await refine.refine("q", hit, 5, Recall())) == 1  # explicit value wins


async def test_word_matches_stay_when_nothing_is_indexed_yet() -> None:
    out = Recall(skipped={"vector": "nothing indexed in this embedding space yet"})
    hits = [_hit("thai words", {"trigram": 1})]
    assert len(await refine.refine("q", hits, 5, out)) == 1
