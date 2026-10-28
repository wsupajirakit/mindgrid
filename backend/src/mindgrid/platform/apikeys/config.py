"""API key and token lifetimes; the clock skew a signature may have."""

from pydantic import PositiveInt

from mindgrid.core.config import AppSettings, env_field, settings_getter


class KeySettings(AppSettings):
    access_ttl_s: PositiveInt = env_field(
        "MINDGRID_ACCESS_TOKEN_TTL_S", 900, doc="Access token lifetime (seconds)."
    )
    refresh_ttl_days: PositiveInt = env_field(
        "MINDGRID_REFRESH_TOKEN_TTL_DAYS", 30, doc="Refresh token lifetime (days)."
    )
    signature_skew_s: PositiveInt = env_field(
        "MINDGRID_SIGNATURE_SKEW_S", 300, doc="Largest allowed clock difference of a signature."
    )
    key_max_days: PositiveInt = env_field(
        "MINDGRID_KEY_MAX_DAYS", 365, doc="Longest lifetime of an API key (days)."
    )


get_settings = settings_getter(KeySettings)
