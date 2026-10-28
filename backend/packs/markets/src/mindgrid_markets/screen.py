"""The full screen in one call: bars -> clock -> universe -> frames -> per-symbol view,
stages, coil and levels -> regime and sectors. The result holds plain JSON values only."""

import math
from typing import Any

import numpy as np
import pandas as pd

from mindgrid.functions.contracts import Frame

from . import bars, clock, prep, regime, stages, views
from .params import MarketParams


def _scalar(value: Any) -> Any:
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating | float):
        f = float(value)
        return None if math.isnan(f) else f
    return str(value) if isinstance(value, pd.Timestamp) else value


def _plain(value: Any) -> Any:
    """numpy / pandas scalars -> Python, NaN -> None, recursively."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    return _scalar(value)


def _week_scale(
    tables: bars.Tables, frames: prep.Frames, uni: dict[str, list[str]], p: MarketParams
) -> float:
    week = next((g.Datetime.iloc[-1] for g in frames.get("1w", {}).values() if len(g)), None)
    if week is None:
        return 1.0
    start = week.normalize() - pd.Timedelta(days=week.weekday())
    return prep.week_scale(tables, start, uni, p)


def _history(hist: dict[str, dict[str, Any]], s: str, has_1d: bool) -> dict[str, Any]:
    sh: dict[str, dict[str, Any]] = {
        tf: {"bars": h["short"][s], "unreliable": clock.unreliable(h["short"][s])}
        for tf, h in hist.items()
        if s in h["short"]
    }
    if "1w" in sh and "1d" not in sh and has_1d:
        est = 5 * sh["1w"]["bars"]  # a new listing: about 5 daily bars per weekly bar
        if est < 200:
            sh["1d"] = {"bars": est, "est": True, "unreliable": clock.unreliable(est)}
    return sh


def _symbol(ctx: dict[str, Any], s: str, p: MarketParams) -> dict[str, Any]:
    frames, mode = ctx["frames"], ctx["mode"]
    v = views.view(frames, s, ctx["wscale"], p)
    src = clock.price_source(ctx["tables"], ctx["asofs"], s)
    v["px_now"] = round(src["px"], 4) if src else None
    v["_px_src"] = src
    if s not in ctx["uni"]["noneq"]:
        v["_stage"] = stages.full(v, frames, p) if mode == "full" else stages.short(v, frames, p)
        if mode == "full":
            v["_stage_ez"] = stages.relaxed(v, frames, p)
        v["_coil"] = views.coil(frames, s, p)
        v["_levels"] = views.levels(frames, s, p)
    sh = _history(ctx["hist"], s, "1d" in ctx["tables"])
    if sh:
        v["_hist"] = sh
    return v


def run(parts: dict[str, list[Frame]], p: MarketParams) -> dict[str, Any]:
    tables, metas = bars.load(parts)
    off = bars.normalize_et(tables)
    asofs = bars.asofs(tables, metas)
    uni = bars.universe(tables, p)
    hist = clock.short_history(tables, metas)
    frames = prep.frames(tables, uni, asofs, p)
    mode = "full" if ("1d" in tables and "1w" in tables) else "short"
    ctx: dict[str, Any] = {
        "tables": tables,
        "asofs": asofs,
        "uni": uni,
        "hist": hist,
        "frames": frames,
        "mode": mode,
        "wscale": _week_scale(tables, frames, uni, p),
    }
    by_symbol = {s: _symbol(ctx, s, p) for s in uni["all"]}
    tick = clock.bar_clock(tables, asofs, metas, p)
    state = {
        "asof_et": str(max(asofs.values())) if asofs else None,
        "asof_by_tf": {tf: str(t) for tf, t in asofs.items()},
        "bar_clock": tick,
        "can_judge_daily_close": bool(tick.get("1d", {}).get("can_judge_daily_close")),
        "meta_by_tf": metas,
        "tz_shift_applied_h": off,
        "wscale": round(ctx["wscale"], 3),
        "universe": uni,
        "screen_mode": mode,
        "short_history": hist,
        "tfs_present": [tf for tf in bars.TFS if tf in tables],
        "checks": bars.checks(tables, off, p),
        "views": by_symbol,
        "regime": regime.regime(by_symbol, uni, p),
        "sectors": regime.sectors(by_symbol, frames, uni, p),
    }
    return _plain(state)
