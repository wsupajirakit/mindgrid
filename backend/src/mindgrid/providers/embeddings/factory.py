"""Build the configured embedder. Gemini needs its key from the caller; the hashing
embedder exists for tests only and refuses to run elsewhere."""

from mindgrid.core import runtime

from .. import config as provider_config
from .base import Embedder
from .gemini import GeminiEmbedder
from .hashing import HashingEmbedder
from .local import LocalEmbedder


class ProviderUnavailableError(RuntimeError):
    """The chosen provider cannot run (missing key, test-only provider in production)."""


def build(gemini_key: str = "") -> Embedder:
    cfg = provider_config.get_settings()
    if cfg.provider == "gemini":
        if not gemini_key:
            raise ProviderUnavailableError("the Gemini embedding provider needs the Gemini key")
        return GeminiEmbedder(gemini_key, cfg.gemini_model, cfg.gemini_dims)
    if cfg.provider == "hashing":
        if runtime.get_settings().environment != "test":
            raise ProviderUnavailableError("the hashing embedder is for tests only")
        return HashingEmbedder()
    return LocalEmbedder(cfg.local_model, cfg.vector_size(), cfg.threads, cfg.cache_dir)
