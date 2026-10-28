"""Database settings. Two roles: the app connects as a role without BYPASSRLS that owns
nothing, so row-level security always applies; migrations connect as the owner role."""

from pydantic import PositiveInt, SecretStr

from mindgrid.core.config import AppSettings, env_field, settings_getter


class DatabaseSettings(AppSettings):
    url: SecretStr | None = env_field(
        "MINDGRID_DATABASE_URL",
        None,
        doc="App connection (postgresql+asyncpg://…), as the non-owner app role.",
    )
    migration_url: SecretStr | None = env_field(
        "MINDGRID_MIGRATION_DATABASE_URL",
        None,
        doc="Owner connection used only by migrations; blank = MINDGRID_DATABASE_URL.",
    )
    app_role: str = env_field(
        "MINDGRID_DB_APP_ROLE",
        "mindgrid_app",
        doc="Name of the app role migrations grant table access to.",
        pattern=r"^[a-z_][a-z0-9_]{0,62}$",
    )
    pool_size: PositiveInt = env_field("MINDGRID_DB_POOL_SIZE", 10, doc="Connections per process.")
    statement_timeout_ms: PositiveInt = env_field(
        "MINDGRID_DB_STATEMENT_TIMEOUT_MS", 15_000, doc="Server-side limit per statement."
    )


get_settings = settings_getter(DatabaseSettings)


def app_url() -> str:
    cfg = get_settings()
    if cfg.url is None:
        raise RuntimeError("MINDGRID_DATABASE_URL is not set")
    return cfg.url.get_secret_value()


def migration_url() -> str:
    cfg = get_settings()
    chosen = cfg.migration_url or cfg.url
    if chosen is None:
        raise RuntimeError("MINDGRID_MIGRATION_DATABASE_URL / MINDGRID_DATABASE_URL not set")
    return chosen.get_secret_value()
