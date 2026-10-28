"""Staging. Full mode (weekly + daily present) is the 4-phase read with the kill switch;
short mode (intraday only) uses 4H structure and the 1H trigger; the relaxed (ez) sibling
splits the kill switch, adds an early-reversal track and widens the RSI band. Stage names
are codes (TRIGGER, SETUP, ...); readers translate them."""

from typing import Any

from .params import MarketParams
from .prep import Frames, ipi
from .views import relative_strength

View = dict[str, Any]


def _trigger(v: View, frames: Frames, p: MarketParams) -> bool:
    """1H trigger: above VWAP on rising OBV with volume and accumulation."""
    h1 = v.get("1h")
    if not h1:
        return False
    g = frames.get("1h", {}).get(v["sym"])
    obv_up = g is not None and len(g) >= 2 and (g.obv_slope.iloc[-1] or 0) > 0
    return bool(
        h1["vwap"]
        and h1["close"] > h1["vwap"]
        and (h1["rvol"] or 0) > p.stage.trigger_rvol
        and obv_up
        and h1["status"] == "Accum"
    )


def _near_ema(tf: dict[str, Any], p: MarketParams) -> bool:
    return (
        tf["close"] <= tf["e20"] * p.stage.near_ema or tf["close"] <= tf["e50"] * p.stage.near_ema
    )


def _rsi_in(tf: dict[str, Any] | None, high: float, p: MarketParams) -> bool:
    return bool(tf and tf["rsi"] and p.stage.rsi_low <= tf["rsi"] <= high)


def _ext(tf: dict[str, Any]) -> float | None:
    return round((tf["close"] / tf["e200"] - 1) * 100, 0) if tf["e200"] else None


def short(v: View, frames: Frames, p: MarketParams) -> dict[str, Any]:
    h4 = v.get("4h")
    if not h4:
        return {"stage": "NO-DATA", "mode": "short"}
    kill = h4["status"] == "Dist"
    struct = h4["gc"] and (h4.get("cmf") or 0) > 0 and not kill
    setup = bool(
        struct and _near_ema(h4, p) and h4["c_gt_e200"] and _rsi_in(h4, p.stage.rsi_high_relaxed, p)
    )
    p4 = _trigger(v, frames, p)
    if kill:
        stage = "KILL-S"
    elif struct and setup and p4:
        stage = "TRIGGER-S"
    elif struct and setup:
        stage = "SETUP-S"
    elif struct:
        stage = "WATCH-S"
    else:
        stage = "FAIL-S"
    return {
        "stage": stage,
        "mode": "short",
        "kill": kill,
        "gc4": h4["gc"],
        "struct": struct,
        "setup": setup,
        "p4": p4,
        "trap6": False,
        "ext200_pct": _ext(h4),
    }


def _trap(v: View, frames: Frames, p: MarketParams) -> bool:
    """Rule-6 trap: a fresh 1H distribution right after accumulation on volume."""
    g, h1 = frames.get("1h", {}).get(v["sym"]), v.get("1h")
    if g is None or len(g) < p.stage.trap_min_bars or not h1:
        return False
    if h1["status"] != "Dist" or (h1["cmf"] or 0) <= 0:
        return False
    prior = g.iloc[-6:-1]
    readings = [ipi(g.iloc[: i + 1], p.flow) for i in range(len(g) - 6, len(g) - 1)]
    return any(
        r["status"] == "Accum" and (prior.rvol.iloc[j] or 0) > p.stage.trap_rvol
        for j, r in enumerate(readings)
    )


def _ladder(kill: bool, p2: bool, p3: bool, p4: bool, p2_loose: bool) -> str:
    if kill:
        return "KILL"
    if p2 and p3 and p4:
        return "TRIGGER"
    if p2 and p3:
        return "SETUP"
    if p2:
        return "MACRO-WATCH"
    if p2_loose and p3:
        return "SETUP(loose)"
    return "WATCH(loose)" if p2_loose else "FAIL"


def full(v: View, frames: Frames, p: MarketParams) -> dict[str, Any]:
    d1, w1, h4 = v.get("1d"), v.get("1w"), v.get("4h")
    if not d1 or not w1:
        return {"stage": "NO-DATA", "reason": "missing 1D/1W bars for this symbol"}
    kill = d1["status"] == "Dist" or w1["status"] == "Dist"
    base = d1["gc"] and w1["gc"] and (w1["cmf"] or 0) > 0 and not kill
    p2 = base and w1["status"] == "Accum"
    rsi_ok = _rsi_in(d1, p.stage.rsi_high, p) or _rsi_in(h4, p.stage.rsi_high, p)
    p3 = bool(_near_ema(d1, p) and d1["c_gt_e200"] and rsi_ok and (d1["cmf"] or 0) > 0)
    p4 = _trigger(v, frames, p)
    return {
        "stage": _ladder(kill, p2, p3, p4, base),
        "kill": kill,
        "p2": p2,
        "p2_loose": base,
        "p3": p3,
        "p4": p4,
        "trap6": _trap(v, frames, p),
        "ext200_pct": _ext(d1),
    }


def relaxed(v: View, frames: Frames, p: MarketParams) -> dict[str, Any]:
    d1, w1, h4 = v.get("1d"), v.get("1w"), v.get("4h")
    if not d1 or not w1:
        return {"stage": "NO-DATA", "ez": True, "reason": "missing 1D/1W"}
    rs60 = relative_strength(frames, v["sym"], p.stage.rs_days, p)
    hard_kill = w1["status"] == "Dist"
    w_accum = w1["status"] == "Accum"
    forgiven = d1["status"] == "Dist" and not hard_kill and w_accum and (rs60 or -1) > 0
    kill = hard_kill or (d1["status"] == "Dist" and not forgiven)
    high = p.stage.rsi_high_relaxed
    rsi_ok = _rsi_in(d1, high, p) or _rsi_in(h4, high, p)
    p3 = bool(_near_ema(d1, p) and d1["c_gt_e200"] and rsi_ok and (d1["cmf"] or 0) > 0)
    base = d1["gc"] and w1["gc"] and (w1["cmf"] or 0) > 0 and not kill
    p2 = base and w_accum
    ext = _ext(d1)
    reversal = bool(
        (not w1["gc"])
        and d1["gc"]
        and (w1["cmf"] or 0) > 0
        and (rs60 or -1) > 0
        and d1["c_gt_e200"]
        and ext is not None
        and ext <= p.stage.reversal_max_ext
        and not hard_kill
    )
    p4 = _trigger(v, frames, p)
    stage = _ladder(kill, p2, p3, p4, base)
    reason = None
    if stage in ("SETUP(loose)", "WATCH(loose)", "FAIL") and reversal:
        stage, reason = "REVERSAL", "early_turn"
    if forgiven and stage not in ("KILL", "FAIL"):
        reason = (reason + "|" if reason else "") + "dip_forgiven"
    return {
        "stage": stage,
        "ez": True,
        "ez_reason": reason,
        "kill": kill,
        "hard_kill": hard_kill,
        "dip_forgiven": forgiven,
        "reversal": reversal,
        "rs60": rs60,
        "p2": p2,
        "p2_loose": base,
        "p3": p3,
        "p4": p4,
        "ext200_pct": ext,
    }
