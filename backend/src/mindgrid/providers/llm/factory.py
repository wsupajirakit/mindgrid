"""Build the writer for an answer mode. `none` has no writer: the caller gets the
Context Pack and writes the answer itself."""

from typing import Literal

from .. import config as provider_config
from .base import Writer
from .gemini import GeminiWriter
from .ollama import OllamaWriter

Mode = Literal["none", "gemini", "local"]


class WriterUnavailableError(RuntimeError):
    """The chosen mode cannot run (missing key)."""


def build(mode: Mode, gemini_key: str = "") -> Writer | None:
    cfg = provider_config.get_llm_settings()
    if mode == "gemini":
        if not gemini_key:
            raise WriterUnavailableError("the Gemini answer mode needs the Gemini key")
        return GeminiWriter(gemini_key, cfg.gemini_model)
    if mode == "local":
        return OllamaWriter(cfg.local_url, cfg.local_model)
    return None
