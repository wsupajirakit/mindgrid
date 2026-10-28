"""Embedder spaces, the test-only embedder and provider selection."""

import math
from collections.abc import Callable

import pytest

from mindgrid.providers.embeddings import factory
from mindgrid.providers.embeddings.base import Space, normalize
from mindgrid.providers.embeddings.hashing import HashingEmbedder
from mindgrid.providers.embeddings.local import LocalEmbedder

pytestmark = pytest.mark.anyio


def test_space_key_names_provider_model_and_size() -> None:
    assert Space("local", "m", 8).key == "local:m@8"


def test_normalize_gives_unit_length() -> None:
    assert math.isclose(sum(v * v for v in normalize([3.0, 4.0])), 1.0)
    assert normalize([0.0, 0.0]) == [0.0, 0.0]


async def test_hashing_is_deterministic_and_similar_for_shared_words() -> None:
    emb = HashingEmbedder(dims=32)
    a, b, c = await emb.embed_documents(["stock radar", "radar stock", "unrelated text"])
    assert a == b
    assert sum(x * y for x, y in zip(a, c, strict=True)) < 1.0
    assert await emb.embed_query("stock radar") == a


def test_factory_picks_the_configured_provider(env: Callable[..., None]) -> None:
    env(MINDGRID_EMBEDDING_PROVIDER="local", MINDGRID_ENV="test")
    assert isinstance(factory.build(), LocalEmbedder)
    env(MINDGRID_EMBEDDING_PROVIDER="hashing")
    assert isinstance(factory.build(), HashingEmbedder)


def test_hashing_refused_outside_tests(env: Callable[..., None]) -> None:
    env(MINDGRID_EMBEDDING_PROVIDER="hashing", MINDGRID_ENV="production")
    with pytest.raises(factory.ProviderUnavailableError):
        factory.build()


def test_gemini_needs_a_key(env: Callable[..., None]) -> None:
    env(MINDGRID_EMBEDDING_PROVIDER="gemini")
    with pytest.raises(factory.ProviderUnavailableError):
        factory.build()
    assert factory.build(gemini_key="k").space.provider == "gemini"


def test_vector_size_follows_the_model(env: Callable[..., None]) -> None:
    from pydantic import ValidationError  # noqa: PLC0415

    from mindgrid.providers import config as provider_config  # noqa: PLC0415

    assert provider_config.get_settings().vector_size() == 768  # EmbeddingGemma by default
    env(MINDGRID_EMBED_LOCAL_MODEL="Qwen/Qwen3-Embedding-0.6B-Q")
    assert provider_config.get_settings().vector_size() == 1024
    env(MINDGRID_EMBED_LOCAL_DIMS="768")  # a size the model does not make: refused up front
    with pytest.raises(ValidationError, match="1024"):
        provider_config.get_settings()
    env(MINDGRID_EMBED_LOCAL_MODEL="someone/unknown-model", MINDGRID_EMBED_LOCAL_DIMS=None)
    with pytest.raises(ValidationError, match="MINDGRID_EMBED_LOCAL_DIMS"):
        provider_config.get_settings()
