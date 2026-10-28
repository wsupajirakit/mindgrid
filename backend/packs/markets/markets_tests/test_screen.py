"""The pack on synthetic bars: stages and flags, setups that respect their floors, codes
instead of prose, parameters that move the result, and the registered functions."""

from typing import Any

from mindgrid_markets import screen, setups
from mindgrid_markets.params import MarketParams

from mindgrid.functions import registry

from .synthetic import frames

P = MarketParams()


def _state() -> dict[str, Any]:
    return screen.run(frames(), P)


def test_universe_and_modes() -> None:
    state = _state()
    assert state["screen_mode"] == "full"
    assert state["universe"]["noneq"] == ["VIX"]
    assert state["universe"]["etfs"] == ["HYG"]
    assert set(state["universe"]["stocks"]) == {"AAA", "BBB"}
    assert set(state["tfs_present"]) == {"1w", "1d", "4h", "1h"}


def test_trends_get_opposite_reads() -> None:
    views = _state()["views"]
    up, down = views["AAA"], views["BBB"]
    assert up["1d"]["gc"]
    assert up["1w"]["c_gt_e200"]
    assert not down["1d"]["gc"]
    assert not down["1d"]["c_gt_e200"]
    assert down["_stage"]["stage"] in {"FAIL", "KILL"}
    assert "_stage" not in views["VIX"]  # non-equity series are not staged


def test_setups_keep_their_floors() -> None:
    views = _state()["views"]
    for v in views.values():
        ts = setups.trade_setup(v, P)
        if not ts:
            continue
        atr = ts["atr"]
        pull = min(x for x in (ts["entry_pullback"], v["px_now"]) if x)
        assert ts["stop"] <= pull - P.setup.stop_atr * atr + 1e-6
        assert ts["stop_tight"] <= ts["pivot"] - P.setup.stop_atr * atr + 1e-6
        assert ts["tp1"] > ts["pivot"]
        assert ts["tp2"] >= ts["tp1"]


def test_regime_returns_codes() -> None:
    regime = _state()["regime"]
    assert regime["permission"]["code"].startswith("regime.")
    assert regime["breadth"]["n"] == 3


def test_parameters_change_the_result() -> None:
    base = setups.trade_setup(_state()["views"]["AAA"], P)
    wider = MarketParams.model_validate({"setup": {"stop_atr": 3.0}})
    moved = setups.trade_setup(screen.run(frames(), wider)["views"]["AAA"], wider)
    assert base
    assert moved
    assert moved["stop"] < base["stop"]


def test_registered_functions_and_playbooks_run() -> None:
    fn = registry.get("markets.screen.run")
    assert fn is not None
    parts = frames()
    out = fn.call({"w1": parts["1w"], "d1": parts["1d"], "h4": parts["4h"], "h1": parts["1h"]})
    state = out.model_dump()["screen"]
    table = registry.get("markets.screen.table")
    assert table is not None
    assert {r["sym"] for r in table.call({"screen": state}).model_dump()["rows"]} == {
        "AAA",
        "BBB",
        "HYG",
        "SPY",
    }
    for fid in (
        "markets.regime.summary",
        "markets.setup.rank_short",
        "markets.setup.coiled_spring",
        "markets.setup.conviction",
    ):
        found = registry.get(fid)
        assert found is not None, fid
        found.call({"screen": state})
