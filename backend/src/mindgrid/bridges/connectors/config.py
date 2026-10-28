"""Connector schedule rules (network rules: core.netguard)."""

from mindgrid.core.config import AppSettings, env_field, settings_getter


class ConnectorSettings(AppSettings):
    min_every_minutes: int = env_field(
        "MINDGRID_CONNECTOR_MIN_EVERY_MINUTES", 5, doc="Shortest schedule interval."
    )


get_settings = settings_getter(ConnectorSettings)
