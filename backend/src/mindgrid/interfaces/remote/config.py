"""Where client profiles and cached tokens live."""

from pathlib import Path

from mindgrid.core.config import AppSettings, env_field, settings_getter


class RemoteSettings(AppSettings):
    config_dir: str = env_field(
        "MINDGRID_CONFIG_DIR", "", doc="Client profiles folder (blank = ~/.config/mindgrid)."
    )
    cache_dir: str = env_field(
        "MINDGRID_CLIENT_CACHE_DIR", "", doc="Token cache folder (blank = ~/.cache/mindgrid)."
    )
    profile: str = env_field(
        "MINDGRID_PROFILE", "default", doc="Client profile used by the CLI and the MCP server."
    )


get_settings = settings_getter(RemoteSettings)


def config_dir() -> Path:
    value = get_settings().config_dir
    return Path(value) if value else Path.home() / ".config" / "mindgrid"


def cache_dir() -> Path:
    value = get_settings().cache_dir
    return Path(value) if value else Path.home() / ".cache" / "mindgrid"
