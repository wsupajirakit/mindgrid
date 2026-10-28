"""Indexing tuning (contextual retrieval)."""

from pydantic import PositiveInt

from mindgrid.core.config import AppSettings, env_field, settings_getter


class IndexSettings(AppSettings):
    context_seconds: PositiveInt = env_field(
        "MINDGRID_INDEX_CONTEXT_SECONDS", 60, doc="Longest wait for one chunk's context line."
    )
    context_max_chars: PositiveInt = env_field(
        "MINDGRID_INDEX_CONTEXT_MAX_CHARS", 400, doc="Longest context line kept per chunk."
    )
    context_outline_chars: PositiveInt = env_field(
        "MINDGRID_INDEX_CONTEXT_OUTLINE_CHARS",
        2000,
        doc="Document outline (its headings) given with each chunk.",
    )
    context_neighbour_chars: PositiveInt = env_field(
        "MINDGRID_INDEX_CONTEXT_NEIGHBOUR_CHARS",
        600,
        doc="Text before and after the chunk given with it.",
    )


get_settings = settings_getter(IndexSettings)
