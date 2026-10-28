"""The market clock read from the data itself: which days the equity market traded, which
bars are closed, whether the daily file already holds the latest close, where each
symbol's current price comes from, and which symbols have too little history."""

import contextlib
from typing import Any, cast

import pandas as pd

from .bars import BAR_HOURS, TFS, Tables
from .params import MarketParams

HISTORY_NEEDS = (
    ("EMA_200", 200),
    ("EMA_100", 100),
    ("EMA_50", 50),
    ("RSI50", 50),
    ("CMF50", 50),
    ("cmf20", 20),
    ("ATR14", 14),
)


def equity_only(d: pd.DataFrame, p: MarketParams) -> pd.DataFrame:
    """Drop the 24-hour series (crypto, FX, rates, commodities): they print bars on
    weekends and holidays and would invent a close on a day the market was shut."""
    if "Symbol" not in d.columns:
        return d
    eq = cast(pd.DataFrame, d[~d.Symbol.isin(p.universe.non_equity)])
    return eq if len(eq) else d


def session_days(d1: pd.DataFrame | None, p: MarketParams) -> set[pd.Timestamp]:
    if d1 is None or not len(d1) or "Symbol" not in d1.columns:
        return set()
    eq = equity_only(d1, p)
    per_day = eq.groupby(eq.Datetime.dt.normalize()).Symbol.nunique()
    return set(per_day[per_day >= p.universe.session_min_symbols].index)


def last_close_due(now: pd.Timestamp, days: set[pd.Timestamp] | None = None) -> pd.Timestamp:
    """The newest 16:00 ET close that must exist at `now` (holidays skipped)."""
    d = cast(pd.Timestamp, now.normalize() + pd.Timedelta(hours=16))
    if now < d:
        d = cast(pd.Timestamp, d - pd.Timedelta(days=1))
    if days:
        for _ in range(15):
            if d.normalize() in days:
                return d
            d = cast(pd.Timestamp, d - pd.Timedelta(days=1))
    while d.weekday() >= 5:
        d = cast(pd.Timestamp, d - pd.Timedelta(days=1))
    return d


def _closed(d: pd.DataFrame) -> pd.DataFrame:
    return cast(pd.DataFrame, d[d.Is_Closed_Bar != False]) if "Is_Closed_Bar" in d else d  # noqa: E712


def _daily(rec: dict[str, Any], asof: pd.Timestamp, have: Any, days: set[pd.Timestamp]) -> None:
    need = last_close_due(asof, days)
    rec["daily_close_due"] = str(need)
    rec["has_latest_daily_close"] = bool(have is not None and have.normalize() >= need.normalize())
    rec["can_judge_daily_close"] = bool(asof >= need and rec["has_latest_daily_close"])
    holidays: list[str] = []
    if days:
        probe = need.normalize() + pd.Timedelta(days=1)
        while probe <= asof.normalize():
            if probe.weekday() < 5 and probe not in days and probe < asof.normalize():
                holidays.append(str(probe.date()))
            probe += pd.Timedelta(days=1)
    rec["market_holidays_skipped"] = holidays


def bar_clock(
    tables: Tables,
    asofs: dict[str, pd.Timestamp],
    metas: dict[str, dict[str, str]],
    p: MarketParams,
) -> dict[str, dict[str, Any]]:
    clock: dict[str, dict[str, Any]] = {}
    newest = max(asofs.values()) if asofs else None
    days = session_days(tables.get("1d"), p)
    for tf, d in tables.items():
        asof, eq = asofs[tf], equity_only(d, p)
        last = eq.Datetime.max()
        closed = _closed(eq)
        last_closed = closed.Datetime.max() if len(closed) else None
        if last_closed is not None or "Is_Closed_Bar" in d:
            forming = last_closed is None or last_closed < last
        else:
            forming = bool(last + pd.Timedelta(hours=BAR_HOURS[tf]) > asof)
        rec: dict[str, Any] = {
            "asof_et": str(asof),
            "market_state": (metas.get(tf) or {}).get("market_state"),
            "last_bar": str(last),
            "last_closed_bar": str(last_closed) if last_closed is not None else None,
            "forming_bar_present": bool(forming),
            "bar_age_min": round((asof - last).total_seconds() / 60),
            "closed_bar_age_min": (
                round((asof - last_closed).total_seconds() / 60)
                if last_closed is not None
                else None
            ),
            "behind_newest_leg_min": round((newest - asof).total_seconds() / 60)
            if newest is not None
            else 0,
        }
        non = d[d.Symbol.isin(p.universe.non_equity)]
        if len(non):
            rec["noneq_last_bar"] = str(non.Datetime.max())
        if tf in ("1h", "4h"):
            rec["complete_through"] = str(asof - pd.Timedelta(hours=BAR_HOURS[tf]))
        if tf == "1d":
            _daily(rec, asof, last_closed if last_closed is not None else last, days)
        clock[tf] = rec
    return clock


def price_source(tables: Tables, asofs: dict[str, pd.Timestamp], s: str) -> dict[str, Any] | None:
    """The newest print for `s` (1h, then 4h, then 1d) with its bar time and state."""
    for tf in ("1h", "4h", "1d"):
        d = tables.get(tf)
        if d is None:
            continue
        g = d[d.Symbol == s]
        if not len(g):
            continue
        row = g.iloc[-1]
        t = row.Datetime
        asof = asofs.get(tf, t + pd.Timedelta(hours=BAR_HOURS[tf]))
        flag = None if "Is_Closed_Bar" not in g else bool(row.Is_Closed_Bar)
        return {
            "px": float(row.Close),
            "src_tf": tf,
            "bar_time": str(t),
            "forming": (not flag)
            if flag is not None
            else bool(t + pd.Timedelta(hours=BAR_HOURS[tf]) > asof),
            "closed_flag": flag,
            "age_min": round((asof - t).total_seconds() / 60),
            "session": str(row.Session) if "Session" in g else None,
        }
    return None


def short_history(tables: Tables, metas: dict[str, dict[str, str]]) -> dict[str, dict[str, Any]]:
    """Per timeframe: the normal bar count and the symbols with fewer (new listings)."""
    out: dict[str, dict[str, Any]] = {}
    for tf, d in tables.items():
        rows = d.groupby("Symbol").size()
        if rows.empty:
            continue
        counts = rows.value_counts()
        norm = int(max(counts.index, key=lambda c: (counts[c], c)))
        expected = (metas.get(tf) or {}).get("bars_expected")  # the exporter header wins
        if expected is not None:
            with contextlib.suppress(ValueError):
                norm = int(expected)
        closed = _closed(d).groupby("Symbol").size()
        out[tf] = {
            "expected": norm,
            "short": {s: int(closed.get(s, default=0) or 0) for s, n in rows.items() if n < norm},
        }
    return out


def unreliable(bars: int) -> list[str]:
    """Indicators whose period is longer than the bars that exist."""
    return [k for k, need in HISTORY_NEEDS if bars < need]


__all__ = [
    "TFS",
    "bar_clock",
    "last_close_due",
    "price_source",
    "session_days",
    "short_history",
    "unreliable",
]
