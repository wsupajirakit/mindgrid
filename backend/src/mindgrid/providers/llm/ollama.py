"""Local writer: an Ollama server on this machine or the server's network (no key, the
passages never leave it). Uses the chat API without streaming."""

from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from .. import config as provider_config
from .base import Prompt, WriterError

# Fewest characters per token over the scripts the passages are in (Thai text runs about
# 2 characters per token on the Qwen tokenizer, English about 4): a safe floor.
CHARS_PER_TOKEN = 1.5


class _Message(BaseModel):
    content: str = ""


class _Reply(BaseModel):
    message: _Message | None = None


class OllamaWriter:
    def __init__(self, base_url: str, model: str) -> None:
        self._url = base_url.rstrip("/") + "/api/chat"
        self._model = model

    @property
    def name(self) -> str:
        return f"local:{self._model}"

    @property
    def max_prompt_chars(self) -> int:
        cfg = provider_config.get_llm_settings()
        room = max(cfg.local_context_tokens - cfg.max_output_tokens, 512)
        return int(room * CHARS_PER_TOKEN)

    def _body(self, prompt: Prompt) -> dict[str, Any]:
        cfg = provider_config.get_llm_settings()
        return {
            "model": self._model,
            "stream": False,
            "think": False,
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            "options": {
                "temperature": cfg.temperature,
                "num_predict": cfg.max_output_tokens,
                "num_ctx": cfg.local_context_tokens,
            },
        }

    async def write(self, prompt: Prompt) -> str:
        timeout = provider_config.get_llm_settings().timeout_seconds
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(self._url, json=self._body(prompt))
                response.raise_for_status()
                reply = _Reply.model_validate_json(response.content)
        except (httpx.HTTPError, ValidationError) as err:
            raise WriterError(f"local model unavailable: {type(err).__name__}") from err
        text = reply.message.content.strip() if reply.message else ""
        if not text:
            raise WriterError("the model returned no text")
        return text
