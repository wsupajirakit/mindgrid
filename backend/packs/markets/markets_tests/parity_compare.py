"""Value-by-value comparison of a source dump with the pack's state (used by the parity
test). Flags compare by truth value (the source may hold None where the pack holds False);
free-text reasons are skipped (the pack returns codes)."""

from typing import Any

from mindgrid_markets import setups
from mindgrid_markets.params import MarketParams

FLAGS = {
    "kill",
    "p2",
    "p2_loose",
    "p3",
    "p4",
    "trap6",
    "struct",
    "setup",
    "gc4",
    "hard_kill",
    "dip_forgiven",
    "reversal",
}
SKIP = {"reason", "ez_reason", "mode", "scope"}
PERMISSION = {
    "RISK-OFF": "regime.risk_off",
    "TRANSITION": "regime.transition",
    "SELECTIVE": "regime.selective",
    "RISK-ON": "regime.risk_on_candidate",
}
VIEW_KEYS = ("1w", "1d", "4h", "1h", "px_now", "_stage", "_stage_ez", "_coil", "_levels", "_hist")


class _Diff:
    def __init__(self) -> None:
        self.checked = 0
        self.found: list[tuple[str, Any, Any]] = []

    def value(self, where: str, a: Any, b: Any) -> None:
        if isinstance(a, dict) and isinstance(b, dict):
            for k in a.keys() & b.keys():
                if k not in SKIP:
                    self.value(f"{where}.{k}", a[k], b[k])
            return
        self.checked += 1
        if where.rsplit(".", 1)[-1] in FLAGS:
            a, b = bool(a), bool(b)
        if isinstance(a, int | float) and isinstance(b, int | float) and not isinstance(a, bool):
            x, y = float(a), float(b)
            ok = abs(x - y) <= 1e-9 * max(1.0, abs(x), abs(y))
        else:
            ok = a == b
        if not ok:
            self.found.append((where, a, b))

    def maybe(self, where: str, a: Any, b: Any) -> None:
        if (a is None) != (b is None):
            self.found.append((where, a, b))
        elif a is not None:
            self.value(where, a, b)


def _views(d: _Diff, src: dict[str, Any], views: dict[str, Any]) -> None:
    if set(src["views"]) != set(views):
        d.found.append(("views.symbols", sorted(src["views"]), sorted(views)))
        return
    for s, v in src["views"].items():
        for key in VIEW_KEYS:
            d.maybe(f"{s}.{key}", v.get(key), views[s].get(key))


def _rankings(d: _Diff, src: dict[str, Any], views: dict[str, Any], p: MarketParams) -> None:
    ranked = setups.rank_short(views, p)
    d.value("rank_short.order", [r["sym"] for r in src["rank_short"]], [r["sym"] for r in ranked])
    d.value("rank_short", {r["sym"]: r for r in src["rank_short"]}, {r["sym"]: r for r in ranked})
    for s, v in views.items():
        d.maybe(f"springs.{s}", src["springs"].get(s), setups.coiled_spring(v, p))
        d.maybe(f"conviction.{s}", src["conviction"].get(s), setups.conviction(v, p))
        d.maybe(f"conviction_ez.{s}", src["conviction_ez"].get(s), setups.conviction(v, p, True))


def compare(
    src: dict[str, Any], state: dict[str, Any], p: MarketParams
) -> tuple[int, list[tuple[str, Any, Any]]]:
    d = _Diff()
    for k in (
        "universe",
        "screen_mode",
        "wscale",
        "tz_shift_applied_h",
        "asof_by_tf",
        "short_history",
        "bar_clock",
    ):
        d.value(k, src[k], state[k])
    _views(d, src, state["views"])
    d.value("regime.metrics", src["regime"]["metrics"], state["regime"]["metrics"])
    d.value("regime.breadth", src["regime"]["breadth"], state["regime"]["breadth"])
    hint = src["regime"]["permission_hint"]
    want = next(code for prefix, code in PERMISSION.items() if hint.startswith(prefix))
    d.value("regime.permission", want, state["regime"]["permission"]["code"])
    d.value(
        "sectors", {r["sym"]: r for r in src["sectors"]}, {r["sym"]: r for r in state["sectors"]}
    )
    d.value(
        "sectors.order", [r["sym"] for r in src["sectors"]], [r["sym"] for r in state["sectors"]]
    )
    _rankings(d, src, state["views"], p)
    return d.checked, d.found
