"""Gemini embeddings (google-genai, imported only when this provider is used). The key is
passed in by the caller (it lives in the sealed secrets store); the vector is truncated
(MRL) and re-normalised."""

from typing import TYPE_CHECKING

from .base import Space, normalize

if TYPE_CHECKING:
    from google import genai


class GeminiEmbedder:
    def __init__(self, api_key: str, model: str, dims: int) -> None:
        self._api_key = api_key
        self._client: genai.Client | None = None
        self._space = Space("gemini", model, dims)

    @property
    def space(self) -> Space:
        return self._space

    async def _embed(self, texts: list[str], task: str) -> list[list[float]]:
        from google import genai  # noqa: PLC0415 — heavy import, only when used
        from google.genai import types  # noqa: PLC0415

        if self._client is None:
            self._client = genai.Client(api_key=self._api_key)
        config = types.EmbedContentConfig(task_type=task, output_dimensionality=self._space.dims)
        result = await self._client.aio.models.embed_content(
            model=self._space.model, contents=list(texts), config=config
        )
        return [normalize(list(e.values or [])) for e in result.embeddings or []]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed(texts, "RETRIEVAL_DOCUMENT")

    async def embed_query(self, text: str) -> list[float]:
        return (await self._embed([text], "RETRIEVAL_QUERY"))[0]
