"""Bars from dataset frames: one table per timeframe (parts concatenated), the export
header per timeframe, the timezone repair for old exports, each timeframe's own as-of,
the universe split (stocks / ETFs / non-equity) and data checks as codes."""

import io
import re
from typing import Any, cast

import pandas as pd

from mindgrid.functions.contracts import Frame

from .params import MarketParams

TFS = ["1w", "1d", "4h", "1h"]
BAR_HOURS = {"1h": 1, "4h": 4, "1d": 24, "1w": 168}
_META = re.compile(r"#\s*([\w]+):\s*(.+)")
Tables = dict[str, pd.DataFrame]


def _text(frame: Frame) -> str:
    return frame.raw.decode("utf-8-sig")


def header(frame: Frame) -> dict[str, str]:
    """`# key: value` lines at the top (a csv-quoted comment line is tolerated)."""
    meta: dict[str, str] = {}
    for line in _text(frame).splitlines():
        probe = line.lstrip('"')
        if not probe.startswith("#"):
            break
        found = _META.match(probe)
        if found:
            meta[found.group(1)] = found.group(2).rstrip('"').strip()
    return meta


def _table(frame: Frame) -> pd.DataFrame:
    lines = [
        ln for ln in _text(frame).splitlines(keepends=True) if not ln.lstrip('"').startswith("#")
    ]
    return pd.read_csv(io.StringIO("".join(lines)))


def load(parts: dict[str, list[Frame]]) -> tuple[Tables, dict[str, dict[str, str]]]:
    """({tf: bars sorted by symbol and time}, {tf: header of its first part})."""
    tables: Tables = {}
    metas: dict[str, dict[str, str]] = {}
    for tf in TFS:
        frames = parts.get(tf) or []
        if not frames:
            continue
        metas[tf] = header(frames[0])
        d = pd.concat([_table(f) for f in frames], ignore_index=True)
        d["Datetime"] = pd.to_datetime(d["Datetime"], format="mixed")
        tables[tf] = d.sort_values(["Symbol", "Datetime"]).reset_index(drop=True)
    return tables, metas


def et_offset(tables: Tables) -> int:
    """Old exports stamped bars at true ET - 7h; daily bars must open at 09:30 ET."""
    if "1d" not in tables:
        return 0
    d = tables["1d"]
    modal = (d.Datetime.dt.hour * 60 + d.Datetime.dt.minute).mode().iloc[0]
    offset_min = (9 * 60 + 30) - modal
    hours = round(offset_min / 60)
    return hours if abs(offset_min - hours * 60) <= 31 and hours != 0 else 0


def normalize_et(tables: Tables) -> int:
    off = et_offset(tables)
    if off:
        for d in tables.values():
            d["Datetime"] = d["Datetime"] + pd.Timedelta(hours=off)
    return off


def asofs(tables: Tables, metas: dict[str, dict[str, str]]) -> dict[str, pd.Timestamp]:
    """Each timeframe's fetch time from its own header, else its newest bar end."""
    out: dict[str, pd.Timestamp] = {}
    for tf, d in tables.items():
        stamp = (metas.get(tf) or {}).get("data_asof_et")
        if stamp:
            try:
                out[tf] = cast(pd.Timestamp, pd.Timestamp(stamp).tz_localize(None))
                continue
            except ValueError, TypeError:
                pass
        out[tf] = cast(pd.Timestamp, d.Datetime.max() + pd.Timedelta(hours=BAR_HOURS[tf]))
    return out


def universe(tables: Tables, p: MarketParams) -> dict[str, list[str]]:
    syms: set[str] = set()
    for d in tables.values():
        syms |= set(d.Symbol.unique())
    noneq = {s for s in syms if s in set(p.universe.non_equity)}
    if "1d" in tables:
        vol = tables["1d"].groupby("Symbol").Volume.sum()
        noneq |= set(vol[vol <= 0].index)  # zero-volume series are index-like
    bench = p.universe.benchmark
    etfs = {s for s in syms - noneq if s in set(p.universe.etfs)} - {bench}
    stocks = syms - noneq - etfs - {bench}
    return {
        "all": sorted(syms),
        "noneq": sorted(noneq),
        "etfs": sorted(etfs),
        "stocks": sorted(stocks),
    }


def checks(tables: Tables, off: int, p: MarketParams) -> list[dict[str, Any]]:
    """Data checks as codes with parameters (translated by the reader)."""
    notes: list[dict[str, Any]] = (
        [{"code": "data.tz_shift", "params": {"hours": off}}] if off else []
    )
    for tf, d in tables.items():
        bad = d[(d.CMF > 1) | (d.CMF < -1)]
        if len(bad):
            notes.append(
                {
                    "code": "data.cmf_out_of_range",
                    "params": {"tf": tf, "symbols": int(bad.Symbol.nunique())},
                }
            )
    notes += _jumps(tables, p)
    sizes = {tf: int(d.Symbol.nunique()) for tf, d in tables.items()}
    if len(set(sizes.values())) > 1:
        notes.append({"code": "data.symbol_counts_differ", "params": sizes})
    missing = [tf for tf in TFS if tf not in tables]
    if missing:
        notes.append({"code": "data.missing_timeframes", "params": {"tfs": missing}})
    return notes


def _jumps(tables: Tables, p: MarketParams) -> list[dict[str, Any]]:
    if "1d" not in tables:
        return []
    found: list[str] = []
    for sym, g in tables["1d"].groupby("Symbol"):
        if sym in set(p.universe.no_split_check):
            continue
        r = (g.Close / g.Close.shift(1)).dropna()
        jumps = r[(r > p.universe.split_up) | (r < p.universe.split_down)]
        if len(jumps):
            i = jumps.index[-1]
            found.append(f"{sym} {g.loc[i, 'Datetime'].date()} x{r[i]:.2f}")
    return [{"code": "data.price_jumps", "params": {"items": found}}] if found else []
