"""Market regime from the same views: macro rows, breadth (golden cross and flow share),
tripwire distances and a permission hint (a code; the analyst makes the final call), and
the sector table ranked by relative strength."""

from typing import Any

from .bars import TFS
from .params import MarketParams
from .prep import Frames

Views = dict[str, dict[str, Any]]


def _macro(views: Views, px: dict[str, float | None], p: MarketParams) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for s in p.universe.macro_rows:
        if s not in views:
            continue
        d1, w1 = views[s].get("1d"), views[s].get("1w")
        prev, now = (d1["close"] if d1 else None), px.get(s)
        out[s] = {
            "px": round(now, 2) if now else None,
            "chg_pct": round((now / prev - 1) * 100, 2) if now and prev else None,
            "gc_d": d1["gc"] if d1 else None,
            "gc_w": w1["gc"] if w1 else None,
            "rsi_d": d1["rsi"] if d1 else None,
            "cmf_d": d1.get("cmf") if d1 else None,
            "cmf20_d": d1.get("cmf20") if d1 else None,
            "ipi_d": d1.get("status") if d1 else None,
            "ipi_w": w1.get("status") if w1 else None,
            "above_e200d": d1["c_gt_e200"] if d1 else None,
        }
    return out


def _breadth(views: Views, uni: dict[str, list[str]]) -> dict[str, Any]:
    scr = uni["stocks"] + uni["etfs"]
    n = len(scr) or 1
    btf = "1d" if any(views.get(s, {}).get("1d") for s in scr) else "4h"

    def share(test: Any) -> int:
        return round(sum(1 for s in scr if test(views.get(s, {}).get(btf, {}))) / n * 100)

    if btf == "1d":
        flagged = [s for s in scr if views.get(s, {}).get("_stage", {}).get("kill")]
    else:
        flagged = [
            s
            for s in scr
            if views.get(s, {}).get("_stage", {}).get("stage") in ("FAIL-S", "KILL-S")
        ]
    return {
        "n": n,
        "base_tf": btf,
        "gc_d_pct": share(lambda t: t.get("gc")),
        "cmf50_pos_pct": share(lambda t: (t.get("cmf") or 0) > 0),
        "cmf20_pos_pct": share(lambda t: (t.get("cmf20") or 0) > 0),
        "kill_count": len(flagged),
        "kill_label": "kill" if btf == "1d" else "4H-fail",
        "kill_list": flagged,
    }


def _tripwires(views: Views, px: dict[str, float | None], p: MarketParams) -> dict[str, Any]:
    r = p.regime
    out: dict[str, Any] = {}
    if px.get("US10Y"):
        out["us10y"] = {"px": px["US10Y"], "level": r.us10y_tripwire}
    if px.get("DXY"):
        out["dxy"] = {"px": px["DXY"], "breakout": r.dxy_breakout, "reject": r.dxy_reject}
    if px.get("WTI"):
        out["wti"] = {"px": px["WTI"], "level": r.wti_tripwire}
    vix, vix3m, vix9d = px.get("VIX"), px.get("VIX3M"), px.get("VIX9D")
    if vix and vix3m:
        out["vix_term"] = {"ratio": round(vix / vix3m, 2), "backwardation": vix > vix3m}
    if vix and vix9d:
        out["vix9d_ratio"] = round(vix9d / vix, 2)
    hyg = views.get("HYG", {}).get("1d")
    if hyg:
        out["hyg_e200d"] = {"close": hyg["close"], "e200": hyg["e200"], "above": hyg["c_gt_e200"]}
    return out


def _permission(
    views: Views, px: dict[str, float | None], breadth: dict[str, Any], p: MarketParams
) -> dict[str, Any]:
    r = p.regime
    levels = [("US10Y", r.us10y_tripwire), ("DXY", r.dxy_breakout), ("WTI", r.wti_tripwire)]
    near = any(abs((px.get(k) or 0) / t - 1) < r.near_tripwire for k, t in levels if px.get(k))
    fired = (
        (px.get("US10Y") or 0) > r.us10y_tripwire
        or (px.get("WTI") or 0) > r.wti_tripwire
        or (px.get("VIX") or 0) > (px.get("VIX3M") or 9e9)
    )
    hyg = views.get("HYG", {}).get("1d")
    hyg_below = bool(hyg and not hyg["c_gt_e200"])
    if fired:
        return {"code": "regime.risk_off", "reasons": ["tripwire_fired"]}
    if near or hyg_below:
        reasons = (["near_tripwire"] if near else []) + (["hyg_below_e200d"] if hyg_below else [])
        return {"code": "regime.transition", "reasons": reasons}
    if breadth["cmf50_pos_pct"] < r.selective_breadth_pct:
        return {"code": "regime.selective", "reasons": ["breadth_below"]}
    return {"code": "regime.risk_on_candidate", "reasons": []}


def regime(views: Views, uni: dict[str, list[str]], p: MarketParams) -> dict[str, Any]:
    px = {s: views.get(s, {}).get("px_now") for s in uni["all"]}
    breadth = _breadth(views, uni)
    return {
        "metrics": _macro(views, px, p),
        "breadth": breadth,
        "tripwires": _tripwires(views, px, p),
        "permission": _permission(views, px, breadth, p),
    }


def sectors(
    views: Views, frames: Frames, uni: dict[str, list[str]], p: MarketParams
) -> list[dict[str, Any]]:
    bench = frames.get("1d", {}).get(p.universe.benchmark)
    names = uni["etfs"] + (["HYG"] if "HYG" in views and "HYG" not in uni["etfs"] else [])
    rows: list[dict[str, Any]] = []
    for s in names:
        v = views.get(s, {})
        row: dict[str, Any] = {
            "sym": s,
            **{f"cmf20_{tf}": v.get(tf, {}).get("cmf20") for tf in TFS},
        }
        d1 = v.get("1d", {})
        row.update(
            {
                "ipi_d": d1.get("status"),
                "ipi_w": v.get("1w", {}).get("status"),
                "gc_d": d1.get("gc"),
                "rsi_d": d1.get("rsi"),
            }
        )
        g = frames.get("1d", {}).get(s)
        if bench is not None and g is not None:
            for days, key in ((20, "rs20"), (60, "rs60")):
                if len(g) > days and len(bench) > days:
                    mine = g.Close.iloc[-1] / g.Close.iloc[-1 - days] - 1
                    theirs = bench.Close.iloc[-1] / bench.Close.iloc[-1 - days] - 1
                    row[key] = round((mine - theirs) * 100, 1)
        rows.append(row)
    rows.sort(key=lambda r: r.get("rs20") or -99, reverse=True)
    return rows
