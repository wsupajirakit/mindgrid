from collections.abc import Callable

import pytest
from pydantic import SecretStr, ValidationError

from mindgrid.core.config import AppSettings, CommaList, env_field, env_names, settings_getter


class _Sample(AppSettings):
    items: CommaList = env_field("MG_TEST_ITEMS", (), doc="list")
    count: int = env_field("MG_TEST_COUNT", 3, "MG_TEST_COUNT_OLD", doc="count", gt=0)
    key: SecretStr = env_field("MG_TEST_KEY", SecretStr(""), doc="secret")


_get = settings_getter(_Sample)


def test_values_lists_fallbacks_and_blank_default(env: Callable[..., None]) -> None:
    env(MG_TEST_ITEMS=" a, ,b ", MG_TEST_COUNT="", MG_TEST_COUNT_OLD=None)
    cfg = _get()
    assert cfg.items == ("a", "b")
    assert cfg.count == 3
    env(MG_TEST_COUNT_OLD="7")
    assert _get().count == 7


def test_bad_value_names_the_variable(env: Callable[..., None]) -> None:
    env(MG_TEST_COUNT="0")
    with pytest.raises(ValidationError, match="MG_TEST_COUNT"):
        _get()


def test_secret_is_masked(env: Callable[..., None]) -> None:
    env(MG_TEST_KEY="very-secret")
    assert "very-secret" not in repr(_get())
    assert env_names(_Sample) == [
        "MG_TEST_ITEMS",
        "MG_TEST_COUNT",
        "MG_TEST_COUNT_OLD",
        "MG_TEST_KEY",
    ]
