"""Security settings. The secret key signs CSRF tokens and is the root of the keys that
encrypt stored secrets; the app refuses to start without 32+ bytes of it."""

from pydantic import PositiveInt, SecretStr, field_validator

from mindgrid.core.config import AppSettings, env_field, settings_getter

MIN_SECRET_BYTES = 32


class SecuritySettings(AppSettings):
    secret_key: SecretStr = env_field(
        "MINDGRID_SECRET_KEY", SecretStr(""), doc="Server secret (32+ bytes). Required."
    )
    signin_limit: PositiveInt = env_field(
        "MINDGRID_SIGNIN_LIMIT", 5, doc="Sign-in attempts per IP + email per window."
    )
    signin_ip_limit: PositiveInt = env_field(
        "MINDGRID_SIGNIN_IP_LIMIT", 20, doc="Sign-in attempts per IP per window."
    )
    signin_window_s: PositiveInt = env_field(
        "MINDGRID_SIGNIN_WINDOW_S", 60, doc="Sign-in rate-limit window (seconds)."
    )

    @field_validator("secret_key")
    @classmethod
    def _long_enough(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if raw and len(raw.encode()) < MIN_SECRET_BYTES:
            raise ValueError(f"MINDGRID_SECRET_KEY must be at least {MIN_SECRET_BYTES} bytes")
        return value


get_settings = settings_getter(SecuritySettings)


def secret_bytes() -> bytes:
    raw = get_settings().secret_key.get_secret_value().encode()
    if len(raw) < MIN_SECRET_BYTES:
        raise RuntimeError("MINDGRID_SECRET_KEY is not set")
    return raw
