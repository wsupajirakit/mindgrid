"""Build the configured reranker (None = keep the fused order)."""

from .. import config as provider_config
from .base import Reranker
from .local import LocalReranker


def build() -> Reranker | None:
    cfg = provider_config.get_rerank_settings()
    if cfg.provider == "none":
        return None
    return LocalReranker(cfg.local_model, cfg.threads, cfg.max_chars)
