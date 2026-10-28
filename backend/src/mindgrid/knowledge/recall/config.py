"""Recall tuning."""

from pydantic import PositiveInt

from mindgrid.core.config import AppSettings, env_field, settings_getter


class RecallSettings(AppSettings):
    default_k: PositiveInt = env_field("MINDGRID_RECALL_K", 8, doc="Passages returned by default.")
    max_k: PositiveInt = env_field("MINDGRID_RECALL_MAX_K", 50, doc="Most passages per request.")
    candidates: PositiveInt = env_field(
        "MINDGRID_RECALL_CANDIDATES", 50, doc="Candidates each retriever adds before fusion."
    )
    rrf_k: PositiveInt = env_field(
        "MINDGRID_RECALL_RRF_K", 60, doc="Reciprocal-rank-fusion constant (higher = flatter)."
    )
    ef_search: PositiveInt = env_field(
        "MINDGRID_RECALL_EF_SEARCH", 100, doc="HNSW search breadth (recall vs. speed)."
    )
    trigram_threshold: float = env_field(
        "MINDGRID_RECALL_TRIGRAM_THRESHOLD",
        0.3,
        doc="Minimum word similarity for the trigram retriever (0-1).",
        ge=0,
        le=1,
    )
    rerank_candidates: PositiveInt = env_field(
        "MINDGRID_RECALL_RERANK_CANDIDATES",
        10,
        doc="Fused passages the reranker re-scores (at least k). Measured on real documents: "
        "10 matched 16 and 20 in quality at a third of the time.",
    )
    min_relevance: float = env_field(
        "MINDGRID_RECALL_MIN_RELEVANCE",
        0.005,
        doc="Reranker probability below which a passage is dropped as unrelated (measured "
        "for bge-reranker-v2-m3: relevant >= 0.011, unrelated <= 0.002).",
        ge=0,
        le=1,
    )
    max_vector_distance: float = env_field(
        "MINDGRID_RECALL_MAX_VECTOR_DISTANCE",
        0.0,
        doc="Without a reranker: a passage without an exact keyword match is dropped beyond "
        "this cosine distance. 0 = the value measured for the embedding model "
        "(EmbeddingGemma-300m 0.71, Qwen3-Embedding-0.6B 0.6, others 0.6).",
        ge=0,
        le=2,
    )
    rewrite_seconds: PositiveInt = env_field(
        "MINDGRID_RECALL_REWRITE_SECONDS",
        20,
        doc="Longest wait for a query rewrite (setting recall.rewrite); then the original "
        "question is searched alone.",
    )
    max_query_chars: PositiveInt = env_field(
        "MINDGRID_RECALL_MAX_QUERY_CHARS", 2000, doc="Longest accepted query."
    )


get_settings = settings_getter(RecallSettings)
