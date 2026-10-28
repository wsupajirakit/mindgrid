"""Synapse limits and where sources may live."""

from pydantic import PositiveInt

from mindgrid.core.config import AppSettings, CommaList, env_field, settings_getter


class SynapseSettings(AppSettings):
    allowed_roots: CommaList = env_field(
        "MINDGRID_SYNAPSE_ALLOWED_ROOTS",
        (),
        doc="Folders a source repository may be in (absolute paths; empty = none allowed).",
    )
    max_file_bytes: PositiveInt = env_field(
        "MINDGRID_SYNAPSE_MAX_FILE_BYTES", 200_000, doc="Largest file read from a source."
    )
    max_items: PositiveInt = env_field(
        "MINDGRID_SYNAPSE_MAX_ITEMS", 200, doc="Most items in one proposal."
    )
    git_timeout_seconds: PositiveInt = env_field(
        "MINDGRID_SYNAPSE_GIT_TIMEOUT", 30, doc="Longest wait for one git command."
    )


get_settings = settings_getter(SynapseSettings)
