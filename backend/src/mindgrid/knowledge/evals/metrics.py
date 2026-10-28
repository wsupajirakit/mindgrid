"""Ranking metrics for one case and their mean over a run.

A case lists what it expects (title or "title#heading" fragments). An empty list means
the question is off-topic: the right result is no passage at all (abstention)."""

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CaseScore:
    hit: float  # 1 when an expected passage is in the top k
    recall: float  # share of the expected passages found in the top k
    mrr: float  # 1 / rank of the first expected passage
    ndcg: float  # rank-discounted gain, normalised by the best possible order
    abstained: bool | None  # off-topic case: returned nothing (None = on-topic case)


def matches(expected: str, title: str, heading: str) -> bool:
    want = expected.casefold()
    if "#" in want:
        want_title, want_heading = want.split("#", 1)
        return want_title in title.casefold() and want_heading in heading.casefold()
    return want in title.casefold() or want in heading.casefold()


def score(expected: list[str], found: list[tuple[str, str]], k: int) -> CaseScore:
    """`found` = (title, heading) of the returned passages, best first (at most k)."""
    if not expected:
        empty = not found
        return CaseScore(float(empty), float(empty), float(empty), float(empty), empty)
    relevant = [any(matches(e, t, h) for e in expected) for t, h in found]
    covered = {e for e in expected if any(matches(e, t, h) for t, h in found)}
    first = next((i for i, r in enumerate(relevant, 1) if r), 0)
    dcg = sum(1 / math.log2(i + 1) for i, r in enumerate(relevant, 1) if r)
    ideal = sum(1 / math.log2(i + 1) for i in range(1, min(len(expected), k) + 1))
    return CaseScore(
        hit=float(first > 0),
        recall=len(covered) / len(expected),
        mrr=1 / first if first else 0.0,
        ndcg=min(dcg / ideal, 1.0) if ideal else 0.0,  # one fragment may match many
        abstained=None,
    )


def summary(scores: list[CaseScore]) -> dict[str, float]:
    on = [s for s in scores if s.abstained is None]
    off = [s for s in scores if s.abstained is not None]

    def mean(values: list[float]) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0

    return {
        "cases": len(scores),
        "hit_at_k": mean([s.hit for s in on]),
        "recall_at_k": mean([s.recall for s in on]),
        "mrr": mean([s.mrr for s in on]),
        "ndcg_at_k": mean([s.ndcg for s in on]),
        "abstention": mean([float(bool(s.abstained)) for s in off]),
    }
