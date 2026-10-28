"""Local cross-encoder (fastembed / ONNX runtime), run in a worker thread; downloaded once
into the same lasting model folder as the embedder."""

import functools
from typing import Any

import anyio

from .. import config as provider_config
from .base import probability


@functools.cache
def _model(name: str, threads: int) -> Any:
    from fastembed.rerank.cross_encoder import TextCrossEncoder  # noqa: PLC0415 — heavy

    return TextCrossEncoder(
        model_name=name, threads=threads, cache_dir=provider_config.models_folder()
    )


class LocalReranker:
    def __init__(self, model: str, threads: int, max_chars: int) -> None:
        self._model_name = model
        self._threads = threads
        self._max_chars = max_chars

    @property
    def name(self) -> str:
        return f"local:{self._model_name}"

    def _run(self, query: str, passages: list[str]) -> list[float]:
        model = _model(self._model_name, self._threads)
        texts = [p[: self._max_chars] for p in passages]
        return [probability(float(s)) for s in model.rerank(query, texts)]

    async def score(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        return await anyio.to_thread.run_sync(self._run, query, passages)
