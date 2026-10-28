"""Typed configuration from the environment (pydantic-settings), one Settings class per
module, declared next to the code that reads it.

* `env_field(name, default, doc=...)` spells the variable out in full (findable by grep)
  and carries the line shown in docs/config-reference.md.
* `settings_getter(cls)` returns a cached accessor, registered for `validate_all()` (run at
  start-up: a malformed value stops the boot with the variable named) and `reset()`
  (tests change the environment between cases).
* A blank value means "use the default". Secrets are SecretStr (masked in repr and logs).
* No other module reads os.environ; tools/check_structure.py enforces it.
"""

import functools
from collections.abc import Callable
from typing import Annotated, Any

from pydantic import AliasChoices, BeforeValidator, Field
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        env_ignore_empty=True,
        frozen=True,
        str_strip_whitespace=True,
    )


def env_field(name: str, default: Any, *fallbacks: str, doc: str, **constraints: Any) -> Any:
    alias = AliasChoices(name, *fallbacks) if fallbacks else name
    return Field(default, validation_alias=alias, description=doc, **constraints)


def env_names(cls: type[BaseSettings]) -> list[str]:
    names: list[str] = []
    for field in cls.model_fields.values():
        alias = field.validation_alias
        names += (
            [str(c) for c in alias.choices] if isinstance(alias, AliasChoices) else [str(alias)]
        )
    return names


def _split_commas(value: object) -> object:
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    return value


# A comma-separated value ("a, b,c") as a tuple of non-empty, stripped parts.
CommaList = Annotated[tuple[str, ...], NoDecode, BeforeValidator(_split_commas)]

_GETTERS: list[Callable[[], AppSettings]] = []


def settings_getter[S: AppSettings](cls: type[S]) -> Callable[[], S]:
    getter = functools.cache(cls)
    _GETTERS.append(getter)
    return getter


def registered() -> list[type[AppSettings]]:
    return [getter.__wrapped__ for getter in _GETTERS]  # type: ignore[attr-defined]


def validate_all() -> None:
    for getter in _GETTERS:
        getter()


def reset() -> None:
    for getter in _GETTERS:
        getter.cache_clear()  # type: ignore[attr-defined]
