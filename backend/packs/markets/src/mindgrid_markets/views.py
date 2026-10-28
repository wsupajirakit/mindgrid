"""One symbol across timeframes: last close, EMA position, RSI, VWAP, ATR, dollar volume
and the IPI reading per timeframe; relative strength against the benchmark; the coil
(base, contraction, ignition) and the structure levels used by setups."""

from typing import Any

import pandas as pd

from .bars import TFS
from .params import MarketParams
from .prep import Frames, ipi


def golden(row: Any) -> bool:
    try:
        return bool(row.Close > row.EMA_50 and row.EMA_50 > row.EMA_200)
    except AttributeError, TypeError:
        return False


def _last(frames: Frames, tf: str, s: str) -> tuple[pd.DataFrame | None, Any]:
    g = frames.get(tf, {}).get(s)
    return (g, g.iloc[-1]) if g is not None and len(g) else (None, None)


def _opt(r: Any, col: str, nd: int, scale: float = 1.0) -> float | None:
    if col not in r or pd.isna(r[col]):
        return None
    return round(float(r[col]) / scale, nd)


def view(frames: Frames, s: str, wscale: float, p: MarketParams) -> dict[str, Any]:
    v: dict[str, Any] = {"sym": s}
    for tf in TFS:
        g, r = _last(frames, tf, s)
        if r is None:
            continue
        reading = ipi(g, p.flow, wscale if tf == "1w" else 1.0)
        v[tf] = {
            "close": round(float(r.Close), 2),
            "gc": golden(r),
            "c_gt_e20": bool(r.Close > r.EMA_20),
            "c_gt_e50": bool(r.Close > r.EMA_50),
            "c_gt_e200": bool(r.Close > r.EMA_200),
            "rsi": round(float(r.RSI), 0) if pd.notna(r.RSI) else None,
            "e20": round(float(r.EMA_20), 2),
            "e50": round(float(r.EMA_50), 2),
            "e200": round(float(r.EMA_200), 2),
            "vwap": round(float(r.VWAP), 2) if pd.notna(r.VWAP) else None,
            "atr": _opt(r, "Atr14", 2),
            "dvol_m": _opt(r, "Dollar_Volume", 0, 1e6),
            **reading,
        }
    return v


def relative_strength(frames: Frames, s: str, days: int, p: MarketParams) -> float | None:
    """Return over `days` daily bars minus the benchmark's, in percent."""
    g = frames.get("1d", {}).get(s)
    bench = frames.get("1d", {}).get(p.universe.benchmark)
    if g is None or bench is None or len(g) <= days or len(bench) <= days:
        return None
    mine = g.Close.iloc[-1] / g.Close.iloc[-1 - days] - 1
    theirs = bench.Close.iloc[-1] / bench.Close.iloc[-1 - days] - 1
    return round((mine - theirs) * 100, 1)


def coil(frames: Frames, s: str, p: MarketParams) -> dict[str, Any] | None:
    c = p.coil
    dd = frames.get("1d", {}).get(s)
    if dd is None or len(dd) < c.min_daily_bars:
        dd = frames.get("4h", {}).get(s)
    hd = frames.get("1h", {}).get(s)
    if dd is None or hd is None or len(dd) < c.min_bars:
        return None
    piv = float(dd.High.tail(c.pivot_bars).max())
    px = float(hd.Close.iloc[-1])
    atr_fast = float((dd.High - dd.Low).tail(c.atr_fast_bars).mean())
    atr_slow = float((dd.High - dd.Low).tail(c.atr_slow_bars).mean())
    atr14 = float(dd.Atr14.iloc[-1]) if "Atr14" in dd and pd.notna(dd.Atr14.iloc[-1]) else atr_slow
    recent = hd.tail(c.ignition_bars)
    ignition = bool(((recent.rvol > c.ignition_rvol) & (recent.cmf20 > 0)).any())
    ext_atr = (px - piv) / atr14 if px > piv else 0
    near = piv * c.near_pivot_low <= px <= piv * c.near_pivot_high
    tag = "EXTENDED" if ext_atr > c.extended_atr else ("NEAR-PIVOT" if near else "")
    if not tag and not (atr_fast < atr_slow and ignition):
        return None
    return {
        "pivot15d": round(piv, 2),
        "dist_pct": round((px / piv - 1) * 100, 1),
        "contracting": atr_fast < atr_slow,
        "ignition": ignition,
        "tag": tag or "COILING",
    }


def levels(frames: Frames, s: str, p: MarketParams) -> dict[str, Any] | None:
    c = p.coil
    dd, base_tf = frames.get("1d", {}).get(s), "1d"
    if dd is None or not len(dd):
        dd, base_tf = frames.get("4h", {}).get(s), "4h"
    hd = frames.get("1h", {}).get(s)
    if dd is None or not len(dd):
        return None
    r = dd.iloc[-1]
    out: dict[str, Any] = {
        "base_tf": base_tf,
        "swing_hi15": round(float(dd.High.tail(c.pivot_bars).max()), 2),
        "swing_hi60": round(float(dd.High.tail(c.swing_long_bars).max()), 2),
        "swing_lo10": round(float(dd.Low.tail(c.swing_low_bars).min()), 2),
        "e20d": round(float(r.EMA_20), 2),
        "e50d": round(float(r.EMA_50), 2),
        "e200d": round(float(r.EMA_200), 2),
        "atr14d": _opt(r, "Atr14", 2),
    }
    if hd is not None and len(hd):
        out["e20_1h"] = round(float(hd.EMA_20.iloc[-1]), 2)
        out["vwap_1h"] = round(float(hd.VWAP.iloc[-1]), 2) if pd.notna(hd.VWAP.iloc[-1]) else None
    return out
