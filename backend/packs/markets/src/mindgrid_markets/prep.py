"""Per-symbol frames ready for reading: forming bars cut (each timeframe by its own
as-of), regular-session bars for equities, and the flow columns recomputed: CMF (system
50 and fast 20), OBV slope and its normalised form, RVOL; plus the IPI reading."""

from typing import Any, cast

import numpy as np
import pandas as pd

from .bars import BAR_HOURS, Tables
from .params import Flow, MarketParams

Frames = dict[str, dict[str, pd.DataFrame]]


def cmf(df: pd.DataFrame, n: int) -> np.ndarray:
    hl = df.High - df.Low
    mfm = np.where(hl <= 0, 0, ((df.Close - df.Low) - (df.High - df.Close)) / hl)
    mfv = mfm * df.Volume
    return (pd.Series(mfv, index=df.index).rolling(n).sum() / df.Volume.rolling(n).sum()).values


def _cut(d: pd.DataFrame, tf: str, cut: pd.Timestamp, noneq: list[str]) -> pd.DataFrame:
    if tf in ("1h", "4h"):
        d = cast(pd.DataFrame, d[d.Datetime + pd.Timedelta(hours=BAR_HOURS[tf]) <= cut])
    if "Is_Closed_Bar" in d:
        d = cast(pd.DataFrame, d[d.Is_Closed_Bar != False])  # noqa: E712
    if tf == "1d":
        # 24-hour series: an evening-stamped daily bar ends 24h later, a morning-stamped
        # one at 16:15 the same day; one that has not ended at the fetch time is dropped.
        ne = d.Symbol.isin(noneq)
        evening = d.Datetime.dt.hour >= 16
        end = (d.Datetime + pd.Timedelta(hours=24)).where(
            evening, d.Datetime.dt.normalize() + pd.Timedelta(hours=16, minutes=15)
        )
        d = cast(pd.DataFrame, d[~(ne & (end > cut))])
    hr = d.Datetime.dt.hour + d.Datetime.dt.minute / 60
    if tf == "1h":
        use = ((hr >= 9.0) & (hr < 16.0)) | d.Symbol.isin(noneq)
    elif tf == "4h":
        use = ((hr >= 8.0) & (hr < 16.0)) | d.Symbol.isin(noneq)
    else:
        use = pd.Series(True, index=d.index)
    return cast(pd.DataFrame, d[use])


def _flow(g: pd.DataFrame, tf: str, f: Flow) -> pd.DataFrame:
    if g.Volume.fillna(0).sum() <= 0:
        for c in ("cmf20", "obv_slope", "obv_norm", "rvol", "CMF"):
            g[c] = np.nan
        return g
    if "CMF" not in g or (g.CMF.abs() > 1).any():
        g["CMF"] = cmf(g, f.cmf_period)
    g["cmf20"] = cmf(g, f.cmf_fast)
    obv = (np.sign(g.Close.diff().fillna(0)) * g.Volume).cumsum()
    slope = obv.diff()
    sd = slope.rolling(f.obv_window, min_periods=f.obv_min_periods).std()
    g["obv_slope"] = slope
    g["obv_norm"] = (slope / sd).clip(-1, 1)
    if tf in ("1h", "4h") and "Rvol_Tod" in g and g.Rvol_Tod.notna().any():
        g["rvol"] = g.Rvol_Tod  # time-of-day RVOL for intraday bars
    else:
        g["rvol"] = (
            g.Volume / g.Volume.rolling(f.rvol_window, min_periods=f.rvol_min_periods).mean()
        )
    return g


def frames(
    tables: Tables, uni: dict[str, list[str]], asofs: dict[str, pd.Timestamp], p: MarketParams
) -> Frames:
    out: Frames = {}
    for tf, d in tables.items():
        cut = _cut(d.copy(), tf, asofs[tf], uni["noneq"])
        per: dict[str, pd.DataFrame] = {}
        for s, g in cut.groupby("Symbol"):
            per[str(s)] = _flow(g.sort_values("Datetime").reset_index(drop=True), tf, p.flow)
        out[tf] = per
    return out


def week_scale(
    tables: Tables, week_start: pd.Timestamp, uni: dict[str, list[str]], p: MarketParams
) -> float:
    """5 / trading days in that week: weekly RVOL of a holiday week is scaled up."""
    if "1d" not in tables:
        return 1.0
    d = tables["1d"]
    eq = cast(pd.DataFrame, d[~d.Symbol.isin(uni["noneq"])])
    bench = p.universe.benchmark
    ref = cast(pd.DataFrame, eq[eq.Symbol == bench]) if (eq.Symbol == bench).any() else eq
    days = cast(
        pd.DataFrame,
        ref[(ref.Datetime >= week_start) & (ref.Datetime < week_start + pd.Timedelta(days=7))],
    )
    n = days.groupby(days.Datetime.dt.date).ngroups
    return 5.0 / n if 0 < n < 5 else 1.0


def ipi(g: pd.DataFrame | None, f: Flow, rvol_scale: float = 1.0) -> dict[str, Any]:
    """IPI of the last usable bar: CMF x w1 + (RVOL - 1) x 100 x w2 + OBV_norm x w3."""
    if g is None or not len(g) or pd.isna(g.CMF.iloc[-1]):
        return {"ipi": None, "status": "no-vol", "cmf": None, "cmf20": None, "rvol": None}
    r = g.iloc[-1]
    rvol = (r.rvol if pd.notna(r.rvol) else 1.0) * rvol_scale
    obv = r.obv_norm if pd.notna(r.obv_norm) else 0
    value = r.CMF * f.ipi_cmf_weight + (rvol - 1) * 100 * f.ipi_rvol_weight + obv * f.ipi_obv_weight
    if rvol < f.low_volume_rvol:
        status = "N/A (low vol)"
    elif value > f.accum_above:
        status = "Accum"
    elif value < f.dist_below:
        status = "Dist"
    else:
        status = "Neut"
    return {
        "ipi": round(float(value), 1),
        "status": status,
        "cmf": round(float(r.CMF), 3),
        "cmf20": round(float(r.cmf20), 3) if pd.notna(r.cmf20) else None,
        "rvol": round(float(rvol), 2),
    }
