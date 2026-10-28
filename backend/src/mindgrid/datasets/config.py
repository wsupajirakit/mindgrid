"""Dataset limits."""

from pydantic import PositiveInt

from mindgrid.core.config import AppSettings, env_field, settings_getter


class DatasetSettings(AppSettings):
    max_bytes: PositiveInt = env_field(
        "MINDGRID_DATASET_MAX_BYTES", 200 * 1024 * 1024, doc="Largest dataset file (raw)."
    )
    keep_versions: PositiveInt = env_field(
        "MINDGRID_DATASET_KEEP_VERSIONS", 30, doc="Versions kept per dataset (older ones go)."
    )


get_settings = settings_getter(DatasetSettings)
