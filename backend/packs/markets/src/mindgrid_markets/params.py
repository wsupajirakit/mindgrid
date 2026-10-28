"""Every threshold the pack uses, grouped by step. Defaults are the values of the source
screen (so parity can be checked); a playbook or a project overrides any of them."""

from pydantic import BaseModel, ConfigDict, Field


class _P(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Universe(_P):
    non_equity: list[str] = Field(
        default_factory=lambda: [
            "BTCUSDT",
            "DXY",
            "US10",
            "US10Y",
            "VIX",
            "VIX3M",
            "VIX9D",
            "WTI",
            "XAUUSD",
            "USDTHB",
            "TICK",
            "NDX",
            "SPX",
            "MOVE",
        ]
    )
    etfs: list[str] = Field(
        default_factory=lambda: [
            "SMH",
            "SOXX",
            "IGV",
            "SKYY",
            "BOTZ",
            "ROBO",
            "PAVE",
            "FIW",
            "UFO",
            "CIBR",
            "XBI",
            "XLF",
            "XLU",
            "XLV",
            "XLK",
            "XLI",
            "XLE",
            "XLRE",
            "COPX",
            "LQD",
            "IYT",
            "XHB",
            "XME",
            "ITA",
            "IWM",
            "SPY",
            "QQQ",
            "HYG",
        ]
    )
    benchmark: str = "SPY"
    macro_rows: list[str] = Field(
        default_factory=lambda: [
            "SPY",
            "NDX",
            "IWM",
            "VIX",
            "VIX9D",
            "VIX3M",
            "US10",
            "US10Y",
            "DXY",
            "USDTHB",
            "XAUUSD",
            "WTI",
            "BTCUSDT",
            "HYG",
            "TICK",
        ]
    )
    no_split_check: list[str] = Field(
        default_factory=lambda: ["TICK", "US10Y", "US10", "VIX", "VIX9D", "VIX3M", "MOVE"]
    )
    split_up: float = 1.8  # close/previous close above this = possible split or data error
    split_down: float = 0.55
    session_min_symbols: int = 20  # a day with fewer equities printing is not a session


class Flow(_P):
    cmf_period: int = 50  # recomputed when the file CMF is out of [-1, 1]
    cmf_fast: int = 20
    obv_window: int = 50
    obv_min_periods: int = 20
    rvol_window: int = 20
    rvol_min_periods: int = 10
    ipi_cmf_weight: float = 100
    ipi_rvol_weight: float = 0.5  # applied to (rvol - 1) * 100
    ipi_obv_weight: float = 50
    accum_above: float = 50
    dist_below: float = -20
    low_volume_rvol: float = 0.3


class Stage(_P):
    near_ema: float = 1.02  # close within 2% above EMA20 or EMA50 = pullback zone
    rsi_low: float = 40
    rsi_high: float = 60
    rsi_high_relaxed: float = 68  # short and relaxed (ez) staging
    trigger_rvol: float = 1.5
    trap_rvol: float = 1.2
    trap_min_bars: int = 10
    rs_days: int = 60
    reversal_max_ext: float = 40  # an "early" reversal already 40% above EMA200 is not early


class Coil(_P):
    pivot_bars: int = 15
    atr_fast_bars: int = 5
    atr_slow_bars: int = 20
    ignition_bars: int = 15
    ignition_rvol: float = 1.2
    extended_atr: float = 1.5
    near_pivot_low: float = 0.98
    near_pivot_high: float = 1.005
    min_daily_bars: int = 25
    min_bars: int = 20
    swing_long_bars: int = 60
    swing_low_bars: int = 10


class Regime(_P):
    us10y_tripwire: float = 4.55
    dxy_breakout: float = 101.8
    dxy_reject: float = 100.0
    wti_tripwire: float = 72.0
    near_tripwire: float = 0.01
    selective_breadth_pct: float = 50


class Setup(_P):
    stop_atr: float = 1.5  # every stop at least this many ATR14 under its entry
    tp1_atr: float = 2.0
    tp2_atr: float = 3.0
    cap_margin_atr: float = 0.5  # a swing high this far above the pivot caps TP1
    rank_max_below_pct: float = 2.5
    rank_max_above_pct: float = 0.5
    rank_ext_free: float = 50


class Spring(_P):
    ext_min: float = -20
    ext_max: float = 12
    max_atr_pct: float = 3.5
    min_rs60: float = -5
    max_rsi: float = 65
    min_upside_pct: float = 8
    fallback_stop_pct: float = 8.0


class Conviction(_P):
    stage_weight: dict[str, float] = Field(
        default_factory=lambda: {
            "TRIGGER": 4,
            "SETUP": 3,
            "REVERSAL": 2.5,
            "MACRO-WATCH": 2,
            "SETUP(loose)": 1.5,
            "WATCH(loose)": 1,
        }
    )
    ext_hard: float = 50
    ext_soft: float = 40
    rs_leader: float = 20


class MarketParams(_P):
    universe: Universe = Field(default_factory=Universe)
    flow: Flow = Field(default_factory=Flow)
    stage: Stage = Field(default_factory=Stage)
    coil: Coil = Field(default_factory=Coil)
    regime: Regime = Field(default_factory=Regime)
    setup: Setup = Field(default_factory=Setup)
    spring: Spring = Field(default_factory=Spring)
    conviction: Conviction = Field(default_factory=Conviction)
