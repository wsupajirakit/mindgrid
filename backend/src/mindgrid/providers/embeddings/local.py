"""Embeddings on this machine (fastembed / ONNX runtime): no key, no data leaves the server.
The model runs in a worker thread so the event loop stays free; it is downloaded once
into a lasting cache folder (not the system temp folder, which is cleared on reboot).
Models that expect prompts around queries or documents get them from PROMPTS (or the
MINDGRID_EMBED_*_TEMPLATE settings)."""

import functools
from typing import Any

import anyio

from .. import config as provider_config
from .base import Space, normalize

# model name fragment -> (query template, document template); "{text}" is the content.
PROMPTS: dict[str, tuple[str, str]] = {
    "qwen3-embedding": (
        "Instruct: Given a question, retrieve passages that answer it\nQuery: {text}",
        "{text}",
    ),
    "embeddinggemma": ("task: search result | query: {text}", "title: none | text: {text}"),
}


@functools.cache
def _model(name: str, threads: int, cache_dir: str) -> Any:
    from fastembed import TextEmbedding  # noqa: PLC0415 — heavy import, only when used

    folder = cache_dir or provider_config.models_folder()
    return TextEmbedding(model_name=name, threads=threads, cache_dir=folder)


def templates(model: str) -> tuple[str, str]:
    cfg = provider_config.get_settings()
    built_in = next((t for key, t in PROMPTS.items() if key in model.lower()), ("{text}", "{text}"))
    return (cfg.query_template or built_in[0], cfg.document_template or built_in[1])


class LocalEmbedder:
    def __init__(self, model: str, dims: int, threads: int, cache_dir: str) -> None:
        self._space = Space("local", model, dims)
        self._args = (model, threads, cache_dir)
        self._query, self._document = templates(model)

    @property
    def space(self) -> Space:
        return self._space

    def _run(self, texts: list[str]) -> list[list[float]]:
        model = _model(*self._args)
        return [normalize([float(x) for x in v]) for v in model.embed(texts)]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        prompted = [self._document.replace("{text}", t) for t in texts]
        return await anyio.to_thread.run_sync(self._run, prompted)

    async def embed_query(self, text: str) -> list[float]:
        prompted = self._query.replace("{text}", text)
        return (await anyio.to_thread.run_sync(self._run, [prompted]))[0]
