"""Reciprocal rank fusion."""

import uuid

from mindgrid.knowledge.recall.service import fuse

A, B, C = (uuid.UUID(int=i) for i in (1, 2, 3))


def test_found_by_two_retrievers_beats_first_place_in_one() -> None:
    fused = fuse({"vector": [A, B], "keyword": [C, B]}, rrf_k=60)
    assert [cid for cid, _ in fused] == [B, A, C]
    assert fused[0][1] == 1 / 62 + 1 / 62


def test_empty_rankings_fuse_to_nothing() -> None:
    assert fuse({"vector": [], "keyword": []}, rrf_k=60) == []
