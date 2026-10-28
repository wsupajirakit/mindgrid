"""Embedding defaults. A project can still choose another embedding space later; vectors
from different spaces are never compared."""

from pathlib import Path
from typing import Literal

from pydantic import NonNegativeInt, PositiveInt, model_validator

from mindgrid.core.config import AppSettings, env_field, settings_getter

# Vector sizes of models whose size is known (a wrong size would fail every indexing job).
KNOWN_DIMS = {
    "google/embeddinggemma-300m": 768,
    "Qwen/Qwen3-Embedding-0.6B": 1024,
    "Qwen/Qwen3-Embedding-0.6B-Q": 1024,
    "intfloat/multilingual-e5-large": 1024,
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2": 768,
}
# Cosine distance beyond which a passage is unrelated to the question, measured per model
# on real documents (EmbeddingGemma-300m: on-topic best <= 0.672 over 22 questions,
# off-topic best >= 0.749 over 12; Qwen3-Embedding-0.6B: <= 0.45 and >= 0.71).
KNOWN_OFF_TOPIC_DISTANCE = {
    "google/embeddinggemma-300m": 0.71,
    "Qwen/Qwen3-Embedding-0.6B": 0.6,
    "Qwen/Qwen3-Embedding-0.6B-Q": 0.6,
}
DEFAULT_OFF_TOPIC_DISTANCE = 0.6


class EmbeddingSettings(AppSettings):
    provider: Literal["local", "gemini", "hashing"] = env_field(
        "MINDGRID_EMBEDDING_PROVIDER",
        "local",
        doc="local (on this machine, no key) | gemini (needs the Gemini key) | hashing (tests)",
    )
    local_model: str = env_field(
        "MINDGRID_EMBED_LOCAL_MODEL",
        "google/embeddinggemma-300m",
        doc="fastembed model. Default EmbeddingGemma-300m (multilingual incl. Thai, Gemma terms; "
        "measured 6x faster than Qwen/Qwen3-Embedding-0.6B-Q at equal reranked quality; "
        "use that one for Apache-2.0).",
    )
    local_dims: NonNegativeInt = env_field(
        "MINDGRID_EMBED_LOCAL_DIMS",
        0,
        doc="Its vector size (0 = the model's known size; must match the model).",
    )
    threads: PositiveInt = env_field(
        "MINDGRID_EMBED_THREADS", 2, doc="CPU threads for local embedding."
    )
    cache_dir: str = env_field(
        "MINDGRID_EMBED_CACHE_DIR",
        "",
        doc="Model download folder (blank = ~/.cache/mindgrid/models).",
    )
    query_template: str = env_field(
        "MINDGRID_EMBED_QUERY_TEMPLATE",
        "",
        doc="Prompt around a query, with {text} (blank = the model's known format).",
    )
    document_template: str = env_field(
        "MINDGRID_EMBED_DOCUMENT_TEMPLATE",
        "",
        doc="Prompt around a document chunk, with {text} (blank = the model's known format).",
    )
    gemini_model: str = env_field(
        "MINDGRID_EMBED_GEMINI_MODEL", "gemini-embedding-2", doc="Gemini embedding model."
    )
    gemini_dims: PositiveInt = env_field(
        "MINDGRID_EMBED_GEMINI_DIMS", 1536, doc="Truncated (MRL) size; pgvector indexes <= 2000."
    )
    batch_size: PositiveInt = env_field("MINDGRID_EMBED_BATCH", 16, doc="Texts per embedding call.")

    @model_validator(mode="after")
    def _known_size(self) -> EmbeddingSettings:
        known = KNOWN_DIMS.get(self.local_model)
        if self.local_dims == 0 and known is None:
            raise ValueError(f"set MINDGRID_EMBED_LOCAL_DIMS: no known size for {self.local_model}")
        if known is not None and self.local_dims not in (0, known):
            raise ValueError(
                f"{self.local_model} makes {known}-value vectors, not {self.local_dims}"
            )
        return self

    def vector_size(self) -> int:
        return self.local_dims or KNOWN_DIMS[self.local_model]

    def off_topic_distance(self) -> float:
        if self.provider != "local":
            return DEFAULT_OFF_TOPIC_DISTANCE
        return KNOWN_OFF_TOPIC_DISTANCE.get(self.local_model, DEFAULT_OFF_TOPIC_DISTANCE)


get_settings = settings_getter(EmbeddingSettings)


def models_folder() -> str:
    """Where local models are downloaded once and kept (a volume in a container)."""
    return get_settings().cache_dir or str(Path.home() / ".cache" / "mindgrid" / "models")


class LlmSettings(AppSettings):
    gemini_model: str = env_field(
        "MINDGRID_LLM_GEMINI_MODEL", "gemini-flash-latest", doc="Gemini model that writes answers."
    )
    local_url: str = env_field(
        "MINDGRID_LLM_LOCAL_URL", "http://127.0.0.1:11434", doc="Ollama server (local mode)."
    )
    local_model: str = env_field("MINDGRID_LLM_LOCAL_MODEL", "qwen3:8b", doc="Ollama model.")
    local_context_tokens: PositiveInt = env_field(
        "MINDGRID_LLM_LOCAL_CONTEXT_TOKENS",
        16384,
        doc="Context window asked of the local model (prompt + answer). Ollama's own default "
        "(4096) silently cuts a longer prompt; the passages are fitted to this window.",
    )
    timeout_seconds: PositiveInt = env_field(
        "MINDGRID_LLM_TIMEOUT_SECONDS", 120, doc="Longest wait for one answer."
    )
    temperature: float = env_field(
        "MINDGRID_LLM_TEMPERATURE", 0.1, doc="Low = sticks to the passages.", ge=0, le=2
    )
    max_output_tokens: PositiveInt = env_field(
        "MINDGRID_LLM_MAX_OUTPUT_TOKENS", 2048, doc="Longest answer."
    )


get_llm_settings = settings_getter(LlmSettings)


class RerankSettings(AppSettings):
    provider: Literal["local", "none"] = env_field(
        "MINDGRID_RERANK_PROVIDER",
        "local",
        doc="local (cross-encoder on this machine, no key) | none (fused order only)",
    )
    local_model: str = env_field(
        "MINDGRID_RERANK_LOCAL_MODEL",
        "BAAI/bge-reranker-v2-m3-int8",
        doc="fastembed cross-encoder (Apache-2.0, multilingual incl. Thai).",
    )
    threads: PositiveInt = env_field(
        "MINDGRID_RERANK_THREADS", 2, doc="CPU threads for local reranking."
    )
    max_chars: PositiveInt = env_field(
        "MINDGRID_RERANK_MAX_CHARS",
        500,
        doc="Start of each passage given to the reranker. Measured on real documents: 500 "
        "matched 700 and 2000 in quality (350 lost hits); cost grows with length.",
    )


get_rerank_settings = settings_getter(RerankSettings)
