"""Reranker scores as probabilities; provider selection."""

import math
from collections.abc import Callable

from mindgrid.providers.rerank import factory
from mindgrid.providers.rerank.base import probability
from mindgrid.providers.rerank.local import LocalReranker


def test_probability_is_a_stable_sigmoid() -> None:
    assert probability(0.0) == 0.5
    assert math.isclose(probability(2.0) + probability(-2.0), 1.0)
    assert probability(-1000.0) == 0.0
    assert probability(1000.0) == 1.0


def test_factory(env: Callable[..., None]) -> None:
    env(MINDGRID_RERANK_PROVIDER="none")
    assert factory.build() is None
    env(MINDGRID_RERANK_PROVIDER="local")
    built = factory.build()
    assert isinstance(built, LocalReranker)
    assert "bge-reranker" in built.name
