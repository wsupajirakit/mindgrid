"""Deterministic multi-timeframe bars for tests: an uptrend, a downtrend, the benchmark,
a credit ETF and a volatility index, with the indicator columns an export carries."""

from typing import cast

import numpy as np
import pandas as pd

from mindgrid.functions.contracts import Frame

SERIES = {"AAA": 0.0012, "BBB": -0.0010, "SPY": 0.0005, "HYG": 0.0002, "VIX": 0.0}


def _indicators(d: pd.DataFrame) -> pd.DataFrame:
    for n in (20, 50, 100, 200):
        d[f"EMA_{n}"] = d.Close.ewm(span=n, adjust=False).mean()
    delta = d.Close.diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=1).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=1).mean()
    d["RSI"] = 100 - 100 / (1 + gain / loss.replace(0, 1e-9))
    hl = d.High - d.Low
    d["CMF"] = (((d.Close - d.Low) - (d.High - d.Close)) / hl * d.Volume).rolling(
        50, min_periods=1
    ).sum() / d.Volume.rolling(50, min_periods=1).sum()
    d["VWAP"] = (d.Close * d.Volume).cumsum() / d.Volume.cumsum()
    d["Atr14"] = hl.rolling(14, min_periods=1).mean()
    d["Dollar_Volume"] = d.Close * d.Volume
    d["Is_Closed_Bar"] = True
    d["Session"] = "RTH"
    return d


def _bars(sym: str, drift: float, times: pd.DatetimeIndex, step: float) -> pd.DataFrame:
    i = np.arange(len(times))
    close = 100 * np.exp(drift * step * i) * (1 + 0.01 * np.sin(i / 7))
    if sym == "VIX":
        close = 15 + 2 * np.sin(i / 9)
    d = pd.DataFrame({"Symbol": sym, "Datetime": times, "Close": close})
    d["Open"] = d.Close.shift(1).fillna(d.Close)
    d["High"] = np.maximum(d.Open, d.Close) * 1.006
    d["Low"] = np.minimum(d.Open, d.Close) * 0.994
    d["Volume"] = 0.0 if sym == "VIX" else 1e6 * (1 + 0.3 * np.cos(i / 5))
    return _indicators(d)


def _times(tf: str, end: pd.Timestamp) -> tuple[pd.DatetimeIndex, float]:
    days = pd.bdate_range(end=end.normalize(), periods=320)
    if tf == "1w":
        return pd.DatetimeIndex(
            days[[d.weekday() == 0 for d in days]][-120:] + pd.Timedelta(hours=9, minutes=30)
        ), 5
    if tf == "1d":
        return pd.DatetimeIndex(days[-300:] + pd.Timedelta(hours=9, minutes=30)), 1
    hours = [8.5, 12.5] if tf == "4h" else [9.5 + h for h in range(7)]
    stamps = [d + pd.Timedelta(minutes=round(h * 60)) for d in days[-60:] for h in hours]
    return pd.DatetimeIndex(stamps), 1 / len(hours)


def frames(end: str = "2026-10-23") -> dict[str, list[Frame]]:
    stamp = cast(pd.Timestamp, pd.Timestamp(end))
    out: dict[str, list[Frame]] = {}
    for tf in ("1w", "1d", "4h", "1h"):
        times, step = _times(tf, stamp)
        table = pd.concat([_bars(s, drift, times, step) for s, drift in SERIES.items()])
        table["Datetime"] = table.Datetime.dt.strftime("%Y-%m-%d %H:%M:%S")
        head = f"# data_asof_et: {end}T20:00:00-04:00\n# market_state: CLOSED\n"
        body = (head + table.to_csv(index=False)).encode()
        out[tf] = [Frame(f"bars-{tf}-part1", 1, body, "text/csv", {})]
    return out
