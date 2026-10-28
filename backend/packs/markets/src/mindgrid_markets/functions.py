"""The pack's engine functions (registered on import through the `mindgrid.functions`
entry point). `markets.screen.run` does the heavy work once; the others read its state."""

from typing import Any

from pydantic import Field

from mindgrid.functions.contracts import Args, Frame, Output
from mindgrid.functions.registry import function

from . import screen, setups
from .params import MarketParams

Row = dict[str, Any]


class ScreenArgs(Args):
    w1: list[Frame | None] = Field(default_factory=list[Frame | None])
    d1: list[Frame | None] = Field(default_factory=list[Frame | None])
    h4: list[Frame | None] = Field(default_factory=list[Frame | None])
    h1: list[Frame | None] = Field(default_factory=list[Frame | None])
    overrides: dict[str, Any] = Field(default_factory=dict[str, Any])  # MarketParams fields


class Screen(Output):
    screen: dict[str, Any]
    data_versions: dict[str, list[str]]


@function(
    "markets.screen.run",
    "Multi-timeframe screen: views, stages, coil, levels, regime, "
    "sectors (one call per data snapshot).",
    ScreenArgs,
    Screen,
)
def run_screen(a: ScreenArgs) -> Screen:
    parts = {
        tf: [f for f in getattr(a, key) if f is not None]
        for tf, key in (("1w", "w1"), ("1d", "d1"), ("4h", "h4"), ("1h", "h1"))
    }
    state = screen.run(parts, MarketParams.model_validate(a.overrides))
    versions = {tf: [f"{f.name}@v{f.version}" for f in fs] for tf, fs in parts.items() if fs}
    return Screen(screen=state, data_versions=versions)


class StateArgs(Args):
    screen: dict[str, Any]
    overrides: dict[str, Any] = Field(default_factory=dict[str, Any])


class Rows(Output):
    rows: list[Row]
    count: int


def _row(s: str, v: dict[str, Any]) -> Row:
    st, ez = v.get("_stage") or {}, v.get("_stage_ez") or {}
    d1, w1 = v.get("1d") or {}, v.get("1w") or {}
    return {
        "sym": s,
        "px": v.get("px_now"),
        "stage": st.get("stage"),
        "stage_ez": ez.get("stage"),
        "ext200_pct": st.get("ext200_pct"),
        "rs60": ez.get("rs60"),
        "trap6": st.get("trap6"),
        "ipi_d": d1.get("status"),
        "ipi_w": w1.get("status"),
        "cmf_w": w1.get("cmf"),
        "rsi_d": d1.get("rsi"),
        "coil": (v.get("_coil") or {}).get("tag"),
        "short_history": bool(v.get("_hist")),
    }


@function(
    "markets.screen.table",
    "One row per screened symbol (stage, relaxed stage, "
    "extension, RS60, flow, coil) for table functions.",
    StateArgs,
    Rows,
)
def screen_table(a: StateArgs) -> Rows:
    noneq = set(a.screen["universe"]["noneq"])
    rows = [_row(s, v) for s, v in a.screen["views"].items() if s not in noneq]
    return Rows(rows=rows, count=len(rows))


class Regime(Output):
    regime: dict[str, Any]
    sectors: list[Row]
    checks: list[Row]
    asof_by_tf: dict[str, str]
    can_judge_daily_close: bool
    screen_mode: str


@function(
    "markets.regime.summary",
    "Regime (macro rows, breadth, tripwires, permission code), sector flow and data checks.",
    StateArgs,
    Regime,
)
def regime_summary(a: StateArgs) -> Regime:
    s = a.screen
    return Regime(
        regime=s["regime"],
        sectors=s["sectors"],
        checks=s["checks"],
        asof_by_tf=s["asof_by_tf"],
        can_judge_daily_close=s["can_judge_daily_close"],
        screen_mode=s["screen_mode"],
    )


class RankArgs(StateArgs):
    top_n: int = Field(20, ge=1, le=500)


@function(
    "markets.setup.rank_short",
    "Names at or just under their pivot with positive 1H flow "
    "(breakout entry, tight stop, structure target).",
    RankArgs,
    Rows,
)
def rank_short(a: RankArgs) -> Rows:
    ranked = setups.rank_short(a.screen["views"], MarketParams.model_validate(a.overrides))
    return Rows(rows=ranked[: a.top_n], count=len(ranked))


class SpringArgs(StateArgs):
    max_risk: float = Field(6.0, ge=0, le=10)


@function(
    "markets.setup.coiled_spring",
    "Not-extended names coiling with quiet accumulation, lowest risk first.",
    SpringArgs,
    Rows,
)
def coiled_springs(a: SpringArgs) -> Rows:
    p = MarketParams.model_validate(a.overrides)
    found = [
        {"sym": s, **r}
        for s, v in a.screen["views"].items()
        if (r := setups.coiled_spring(v, p)) is not None and r["risk_score"] <= a.max_risk
    ]
    found.sort(key=lambda r: (r["risk_score"], r["sym"]))
    return Rows(rows=found, count=len(found))


class ConvictionArgs(StateArgs):
    min_score: float = Field(6.0, ge=0, le=10)
    relaxed: bool = False


@function(
    "markets.setup.conviction",
    "Conviction 0-10 from stage, multi-timeframe flow, pivot distance, RS and extension.",
    ConvictionArgs,
    Rows,
)
def conviction(a: ConvictionArgs) -> Rows:
    p = MarketParams.model_validate(a.overrides)
    found = [
        {"sym": s, **r}
        for s, v in a.screen["views"].items()
        if (r := setups.conviction(v, p, a.relaxed)) is not None and r["score"] >= a.min_score
    ]
    found.sort(key=lambda r: (-r["score"], r["sym"]))
    return Rows(rows=found, count=len(found))
