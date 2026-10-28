"""Dataset file reading and the connector network guard."""

from collections.abc import Callable

import pytest

from mindgrid.bridges.connectors import fetch
from mindgrid.datasets import formats

pytestmark = pytest.mark.anyio
CSV = (
    "﻿# data_asof_utc: 2026-10-23T21:31:22Z\n"
    "# tz_base: America/New_York | dst_active: true\n"
    "Symbol,Close,Volume,Flag,Note\n"
    "AAA,10.5,100,True,\n"
    "BBB,-2e3,7,False,x\n"
).encode()


def test_csv_meta_numbers_and_empty_cells() -> None:
    parsed = formats.parse(CSV, "text/csv")
    assert parsed.meta == {
        "data_asof_utc": "2026-10-23T21:31:22Z",
        "tz_base": "America/New_York",
        "dst_active": "true",
    }
    assert parsed.columns == ["Symbol", "Close", "Volume", "Flag", "Note"]
    assert parsed.rows[0] == {
        "Symbol": "AAA",
        "Close": 10.5,
        "Volume": 100,
        "Flag": True,
        "Note": None,
    }
    assert parsed.rows[1]["Close"] == -2000.0


def test_json_records_path_and_ndjson() -> None:
    body = b'{"data": {"items": [{"a": 1}, {"a": 2, "b": "x"}]}}'
    parsed = formats.parse(body, "application/json", "data.items")
    assert (parsed.columns, len(parsed.rows)) == (["a", "b"], 2)
    assert formats.parse(b'{"a":1}\n\n{"a":2}\n', "application/x-ndjson").rows[1] == {"a": 2}
    with pytest.raises(formats.FormatError):
        formats.parse(body, "application/json", "data.missing")


async def test_guard_refuses_plain_http_and_private_hosts(env: Callable[..., None]) -> None:
    with pytest.raises(fetch.FetchError, match="https"):
        await fetch.check_target("http://example.com/x")
    with pytest.raises(fetch.FetchError, match="non-public"):
        await fetch.check_target("https://127.0.0.1/x")
    env(MINDGRID_OUTBOUND_ALLOW_PRIVATE_HOSTS="127.0.0.1")
    await fetch.check_target("http://127.0.0.1:8/x")


def test_column_oriented_json_becomes_rows() -> None:
    body = b'{"daily": {"time": ["2026-10-27", "2026-10-28"], "t_max": [33.6, 34.1]}, "x": 1}'
    parsed = formats.parse(body, "application/json", "daily")
    assert parsed.rows == [
        {"time": "2026-10-27", "t_max": 33.6},
        {"time": "2026-10-28", "t_max": 34.1},
    ]
    assert parsed.columns == ["time", "t_max"]
    with pytest.raises(formats.FormatError):
        formats.parse(b'{"d": {"a": [1, 2], "b": [1]}}', "application/json", "d")
