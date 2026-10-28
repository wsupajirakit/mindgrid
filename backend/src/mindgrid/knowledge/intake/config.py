"""Intake limits and chunking (recursive ~512-token chunks were the strongest default in
the 2026 benchmarks; the embedding model matters more than the splitting method)."""

from pydantic import PositiveInt

from mindgrid.core.config import AppSettings, env_field, settings_getter


class IntakeSettings(AppSettings):
    max_upload_bytes: PositiveInt = env_field(
        "MINDGRID_MAX_UPLOAD_BYTES", 25 * 1024 * 1024, doc="Largest document upload (bytes)."
    )
    chunk_chars: PositiveInt = env_field(
        "MINDGRID_CHUNK_CHARS", 2000, doc="Target chunk size in characters (~512 tokens)."
    )
    chunk_overlap_chars: PositiveInt = env_field(
        "MINDGRID_CHUNK_OVERLAP_CHARS", 250, doc="Characters repeated between chunks."
    )
    pdf_max_pages: PositiveInt = env_field(
        "MINDGRID_PDF_MAX_PAGES", 2000, doc="Pages read from one PDF at most."
    )
    csv_rows_per_chunk: PositiveInt = env_field(
        "MINDGRID_CSV_ROWS_PER_CHUNK", 25, doc="CSV rows per chunk (knowledge mode)."
    )


get_settings = settings_getter(IntakeSettings)
