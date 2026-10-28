"""Process-wide runtime settings."""

from typing import Literal

from mindgrid.core.config import AppSettings, env_field, settings_getter

LogLevel = Literal["debug", "info", "warning", "error"]


class RuntimeSettings(AppSettings):
    environment: Literal["development", "test", "production"] = env_field(
        "MINDGRID_ENV", "development", doc="Deployment environment."
    )
    log_level: LogLevel = env_field("MINDGRID_LOG_LEVEL", "info", doc="Minimum log level.")
    log_json: bool = env_field(
        "MINDGRID_LOG_JSON", True, doc="JSON log lines (off = readable console lines)."
    )
    docs: bool = env_field("MINDGRID_DOCS", True, doc="Serve the OpenAPI docs at /docs.")


get_settings = settings_getter(RuntimeSettings)
