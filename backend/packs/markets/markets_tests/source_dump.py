"""Run by the SOURCE system's Python (not the engine's): dump its screen results (views,
stages, coil, levels, regime, sectors, rankings) for one CSV folder as JSON.
Usage: python source_dump.py <folder with radar_lib.py> <csv folder> <out.json>"""

import json
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, sys.argv[1])
import numpy as np
import radar_lib as rl  # pyright: ignore[reportMissingImports]


def plain(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): plain(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [plain(v) for v in x]
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.floating | float):
        return None if math.isnan(float(x)) else float(x)
    return x


def main() -> None:
    state = rl.run_screen(sys.argv[2])
    views = state["views"]
    keys = (
        "asof_by_tf",
        "bar_clock",
        "universe",
        "screen_mode",
        "wscale",
        "tz_shift_applied_h",
        "short_history",
        "regime",
        "sectors",
    )
    out = {k: state[k] for k in keys}
    out["views"] = views
    out["rank_short"] = rl.rank_short(views)
    out["springs"] = {s: rl.coiled_spring(v) for s, v in views.items()}
    out["conviction"] = {s: rl.conviction(v) for s, v in views.items()}
    out["conviction_ez"] = {s: rl.conviction(v, use_ez=True) for s, v in views.items()}
    Path(sys.argv[3]).write_text(json.dumps(plain(out), default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
