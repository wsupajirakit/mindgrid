"""Session lifetime (OWASP Session Management: absolute and idle timeouts)."""

from pydantic import PositiveInt

from mindgrid.core.config import AppSettings, env_field, settings_getter


class SessionSettings(AppSettings):
    ttl_hours: PositiveInt = env_field(
        "MINDGRID_SESSION_TTL_HOURS", 12, doc="Absolute session lifetime (hours)."
    )
    idle_minutes: PositiveInt = env_field(
        "MINDGRID_SESSION_IDLE_MINUTES", 60, doc="Session ends after this long unused (minutes)."
    )
    touch_every_s: PositiveInt = env_field(
        "MINDGRID_SESSION_TOUCH_EVERY_S", 60, doc="Least time between last-seen writes (s)."
    )


get_settings = settings_getter(SessionSettings)
