"""Setups from structure only: entry (breakout = 15-bar pivot, pullback = 1H EMA20 / VWAP
/ daily EMA20, never above the price), stops at least `stop_atr` ATR14 under each entry,
targets capped by the nearest real swing high; then three rankings: near-pivot readiness,
coiled spring (low-risk, not extended) and conviction (stage + flow alignment)."""

import math
from typing import Any

from .params import MarketParams

View = dict[str, Any]
DEAD = ("FAIL", "FAIL-S", "NO-DATA")


def _floor2(x: float) -> float:
    """Round a stop down to the cent so rounding never pulls it inside the ATR floor."""
    return math.floor(x * 100 + 1e-9) / 100


def _pivot(v: View) -> float | None:
    return (v.get("_coil") or {}).get("pivot15d") or (v.get("_levels") or {}).get("swing_hi15")


def trade_setup(v: View, p: MarketParams) -> dict[str, Any] | None:
    s, lv = p.setup, v.get("_levels") or {}
    px, atr, piv = v.get("px_now"), lv.get("atr14d"), _pivot(v)
    if not (px and atr and piv):
        return None
    pull = lv.get("e20_1h") or lv.get("vwap_1h") or lv.get("e20d")
    base = min(x for x in (pull, px) if x)
    stop, stop_tight = _floor2(base - s.stop_atr * atr), _floor2(piv - s.stop_atr * atr)
    tp1, tp2 = piv + s.tp1_atr * atr, piv + s.tp2_atr * atr
    hi60 = lv.get("swing_hi60")
    if hi60 and piv + s.cap_margin_atr * atr < hi60 < tp1:
        tp1 = hi60
    tp1, tp2 = round(tp1, 2), round(tp2, 2)
    rr1 = round((tp1 - base) / (base - stop), 2) if base > stop and tp1 > base else None
    rr_break = round((tp1 - piv) / (piv - stop_tight), 2) if piv > stop_tight else None
    return {
        "pivot": piv,
        "dist_to_pivot_pct": round((px / piv - 1) * 100, 1),
        "entry_breakout": piv,
        "entry_pullback": pull,
        "stop": stop,
        "stop_tight": stop_tight,
        "tp1": tp1,
        "tp2": tp2,
        "rr_to_tp1": rr1,
        "rr_breakout": rr_break,
        "atr": atr,
        "ext200_pct": (v.get("_stage") or {}).get("ext200_pct"),
    }


def rank_short(views: dict[str, View], p: MarketParams) -> list[dict[str, Any]]:
    """Live names at or just under their pivot with positive 1H flow, best first."""
    s, out = p.setup, []
    for sym, v in views.items():
        st = (v.get("_stage") or {}).get("stage") or ""
        ts = trade_setup(v, p) if not (st.startswith("KILL") or st in DEAD) else None
        if not ts:
            continue
        d = ts["dist_to_pivot_pct"]
        h1 = v.get("1h") or {}
        cmf, rvol = (h1.get("cmf20") or 0), (h1.get("rvol") or 0)
        if d > s.rank_max_above_pct or d < -s.rank_max_below_pct or cmf <= 0:
            continue
        ext = ts.get("ext200_pct") or 0
        score = -abs(d) + cmf * 2 + min(rvol, 3) * 0.5 - max(0, ext - s.rank_ext_free) / 50
        out.append(
            {
                "sym": sym,
                "stage": st,
                "dist_pct": d,
                "cmf1h": cmf,
                "rvol1h": rvol,
                "ext200": ext,
                "score": round(score, 2),
                "entry_breakout": ts["entry_breakout"],
                "entry_pullback": ts["entry_pullback"],
                "stop": ts["stop_tight"],
                "tp1": ts["tp1"],
                "tp2": ts["tp2"],
                "rr_to_tp1": ts["rr_breakout"],
            }
        )
    out.sort(key=lambda x: -x["score"])
    return out


def _spring_gates(v: View, p: MarketParams) -> dict[str, Any] | None:
    d1, w1 = v.get("1d"), v.get("1w")
    ext = (v.get("_stage") or {}).get("ext200_pct")
    if not d1 or not w1 or ext is None:
        return None
    g, lv, px = p.spring, v.get("_levels") or {}, v.get("px_now")
    atr, coil = lv.get("atr14d"), v.get("_coil")
    rs60 = (v.get("_stage_ez") or {}).get("rs60")
    atr_pct = (atr / px * 100) if (atr and px) else None
    swing = lv.get("swing_hi60") or lv.get("swing_hi15")
    upside = round((swing / px - 1) * 100, 0) if (swing and px) else None
    ok = (
        g.ext_min <= ext <= g.ext_max
        and w1["status"] != "Dist"
        and ((w1.get("cmf") or 0) > 0 or (d1.get("cmf20") or 0) > 0)
        and (coil is not None or (atr_pct is not None and atr_pct <= g.max_atr_pct))
        and rs60 is not None
        and rs60 > g.min_rs60
        and (d1.get("rsi") or 100) < g.max_rsi
        and upside is not None
        and upside >= g.min_upside_pct
    )
    if not ok:
        return None
    return {"ext": ext, "rs60": rs60, "atr_pct": atr_pct, "upside": upside, "atr": atr, "px": px}


def _spring_stop(
    v: View, gates: dict[str, Any], p: MarketParams
) -> tuple[Any, float, dict[str, Any] | None]:
    lv, px, atr = v.get("_levels") or {}, gates["px"], gates["atr"]
    ts = trade_setup(v, p)
    entry = (ts or {}).get("entry_pullback") or lv.get("e20d") or px
    stop = (entry - atr) if (entry and atr) else lv.get("e50d")
    if stop is not None and lv.get("e50d"):
        stop = min(stop, lv["e50d"])
    if stop is not None and px and stop >= px:
        stop = round(px - atr, 2) if atr else round(px * 0.94, 2)
    stop = round(stop, 2) if stop is not None else None
    dist = ((px - stop) / px * 100) if (px and stop and px > stop) else p.spring.fallback_stop_pct
    if stop is not None and entry and atr:
        stop = _floor2(min(stop, entry - p.setup.stop_atr * atr))
    return stop, dist, ts


def coiled_spring(v: View, p: MarketParams) -> dict[str, Any] | None:
    gates = _spring_gates(v, p)
    if gates is None:
        return None
    stop, dist, ts = _spring_stop(v, gates, p)
    d1, w1, coil = v["1d"], v["1w"], v.get("_coil")
    risk = min(3.0, dist / 3) + min(3.0, abs(gates["ext"]) / 7)
    risk -= 1.5 if w1["status"] == "Accum" else 0
    risk -= 1.0 if d1.get("c_gt_e200") else 0
    risk += 1.0 if (d1.get("rvol") or 1) < 0.5 else 0
    if coil and coil.get("dist_pct") is not None:
        risk += min(1.5, abs(coil["dist_pct"]) / 8)
    risk = max(0.0, min(10.0, round(risk, 1)))
    return {
        "ext200": gates["ext"],
        "rs60": gates["rs60"],
        "atr_pct": round(gates["atr_pct"], 1) if gates["atr_pct"] else None,
        "coil_tag": (coil or {}).get("tag"),
        "w1": w1["status"],
        "d1_cmf20": d1.get("cmf20"),
        "rsi": d1.get("rsi"),
        "risk_score": risk,
        "upside_to_swinghi_pct": gates["upside"],
        "pivot": ts["pivot"] if ts else None,
        "entry_pullback": (ts or {}).get("entry_pullback"),
        "stop": stop,
        "tp1": (ts or {}).get("tp1"),
        "tp2": (ts or {}).get("tp2"),
    }


def conviction(v: View, p: MarketParams, relaxed: bool = False) -> dict[str, Any] | None:
    c = p.conviction
    stg = (v.get("_stage_ez") if relaxed else v.get("_stage")) or {}
    st = stg.get("stage")
    if not st or st.startswith("KILL") or st in DEAD:
        return None
    d1, w1, h1 = v.get("1d") or {}, v.get("1w") or {}, v.get("1h") or {}
    ts = trade_setup(v, p)
    sc = c.stage_weight.get(st, 0)
    sc += 1.5 if (w1.get("cmf") or 0) > 0 else 0
    sc += 1 if w1.get("status") == "Accum" else 0
    sc += 1 if (d1.get("cmf20") or 0) > 0 else 0
    sc += 0.5 if (h1.get("cmf20") or 0) > 0 else 0
    if ts and ts.get("dist_to_pivot_pct") is not None:
        dd = ts["dist_to_pivot_pct"]
        sc += 1.5 if -3 <= dd <= 0.5 else (0.5 if -6 <= dd < -3 else 0)
    sc += 1 if (stg.get("rs60") or 0) > c.rs_leader else 0
    ext = stg.get("ext200_pct") or 0
    sc -= 2 if ext > c.ext_hard else (1 if ext > c.ext_soft else 0)
    sc -= 0.5 if (h1.get("rvol") or 0) < 0.5 else 0
    return {
        "score": max(0.0, min(10.0, round(sc, 1))),
        "stage": st,
        "ez": relaxed,
        "ts": ts,
        "rs60": stg.get("rs60"),
        "ext200": ext,
    }
