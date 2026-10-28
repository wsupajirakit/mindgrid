"""Gemini writer (google-genai, imported only when used). The key comes from the caller."""

from typing import TYPE_CHECKING

from .. import config as provider_config
from .base import Prompt, WriterError

if TYPE_CHECKING:
    from google import genai


class GeminiWriter:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client: genai.Client | None = None

    @property
    def name(self) -> str:
        return f"gemini:{self._model}"

    @property
    def max_prompt_chars(self) -> int | None:
        return None  # a context of a million tokens: far above any Context Pack

    async def write(self, prompt: Prompt) -> str:
        from google import genai  # noqa: PLC0415 — heavy import, only when used
        from google.genai import types  # noqa: PLC0415

        cfg = provider_config.get_llm_settings()
        if self._client is None:
            self._client = genai.Client(api_key=self._api_key)
        config = types.GenerateContentConfig(
            system_instruction=prompt.system,
            temperature=cfg.temperature,
            max_output_tokens=cfg.max_output_tokens,
        )
        result = await self._client.aio.models.generate_content(
            model=self._model, contents=prompt.user, config=config
        )
        if not result.text:
            raise WriterError("the model returned no text")
        return result.text
