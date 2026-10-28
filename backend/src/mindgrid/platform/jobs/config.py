"""Worker timing."""

from pydantic import PositiveFloat, PositiveInt

from mindgrid.core.config import AppSettings, env_field, settings_getter


class JobSettings(AppSettings):
    lease_seconds: PositiveInt = env_field(
        "MINDGRID_JOB_LEASE_SECONDS",
        600,
        doc="A claimed job not finished within this time is given to another worker.",
    )
    max_attempts: PositiveInt = env_field(
        "MINDGRID_JOB_MAX_ATTEMPTS", 5, doc="Tries before a job is marked failed."
    )
    retry_base_seconds: PositiveInt = env_field(
        "MINDGRID_JOB_RETRY_BASE_SECONDS", 30, doc="First retry delay; doubles each attempt."
    )
    idle_seconds: PositiveFloat = env_field(
        "MINDGRID_JOB_IDLE_SECONDS", 2.0, doc="Worker pause when the queue is empty."
    )


get_settings = settings_getter(JobSettings)
