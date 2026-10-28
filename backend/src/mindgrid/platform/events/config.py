"""Event delivery settings."""

from pydantic import PositiveFloat, PositiveInt

from mindgrid.core.config import AppSettings, CommaList, env_field, settings_getter


class EventSettings(AppSettings):
    public_url: str = env_field(
        "MINDGRID_PUBLIC_URL",
        "http://localhost:8700",
        doc="Base URL receivers use to reach this server (links in events, dataschema).",
    )
    retry_seconds: CommaList = env_field(
        "MINDGRID_EVENT_RETRY_SECONDS",
        ("5", "300", "1800", "7200", "18000", "36000", "50400", "72000", "86400"),
        doc="Wait before each retry (Standard Webhooks schedule, about 3 days in total).",
    )
    timeout_seconds: PositiveFloat = env_field(
        "MINDGRID_EVENT_TIMEOUT_SECONDS", 15, doc="Longest wait for a receiver's answer."
    )
    max_data_bytes: PositiveInt = env_field(
        "MINDGRID_EVENT_MAX_DATA_BYTES", 20_000, doc="Largest event `data` (thin events link out)."
    )
    disable_after_dead: PositiveInt = env_field(
        "MINDGRID_EVENT_DISABLE_AFTER_DEAD",
        5,
        doc="A subscription is switched off after this many dead deliveries in a row.",
    )
    keep_days: PositiveInt = env_field(
        "MINDGRID_EVENT_KEEP_DAYS", 30, doc="Days events and their deliveries are kept."
    )
    batch: PositiveInt = env_field("MINDGRID_EVENT_BATCH", 20, doc="Deliveries claimed per pass.")
    every_seconds: PositiveFloat = env_field(
        "MINDGRID_EVENT_EVERY_SECONDS", 2, doc="How often the worker looks for due deliveries."
    )


get_settings = settings_getter(EventSettings)
