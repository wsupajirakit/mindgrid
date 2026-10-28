"""Parity with the source screen: the pack and the source run on the same CSV folder and
every compared value must match (stages, flags, views, coil, levels, regime, sectors and
the three rankings). Runs only when pointed at the source:
  MINDGRID_PARITY_SOURCE_LIB     folder holding the source radar_lib.py
  MINDGRID_PARITY_SOURCE_PYTHON  the source's Python (with its pandas)
  MINDGRID_PARITY_CSV_DIR        the CSV folder (ztrade_export_<tf>_part<n>.csv)
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from mindgrid_markets import screen
from mindgrid_markets.params import MarketParams

from mindgrid.functions.contracts import Frame

from .parity_compare import compare

ENV = ("MINDGRID_PARITY_SOURCE_LIB", "MINDGRID_PARITY_SOURCE_PYTHON", "MINDGRID_PARITY_CSV_DIR")
pytestmark = [
    pytest.mark.parity,
    pytest.mark.skipif(not all(os.environ.get(k) for k in ENV), reason="set " + ", ".join(ENV)),
]


def _source(tmp: Path) -> dict[str, Any]:
    lib, python, csv_dir = (os.environ[k] for k in ENV)
    out = tmp / "source.json"
    script = Path(__file__).with_name("source_dump.py")
    command = [python, "-I", str(script), lib, csv_dir, str(out)]  # paths set by the operator
    env = {**os.environ, "OMP_NUM_THREADS": "1"}
    subprocess.run(command, check=True, capture_output=True, env=env)  # noqa: S603
    return json.loads(out.read_text())


def test_pack_matches_the_source(tmp_path: Path) -> None:
    csv_dir = Path(os.environ["MINDGRID_PARITY_CSV_DIR"])
    parts = {
        tf: [
            Frame(f.name, 1, f.read_bytes(), "text/csv", {})
            for f in sorted(csv_dir.glob(f"ztrade_export_{tf}_part*.csv"))
        ]
        for tf in ("1w", "1d", "4h", "1h")
    }
    p = MarketParams()
    checked, diffs = compare(_source(tmp_path), screen.run(parts, p), p)
    assert checked > 10_000
    assert diffs == [], diffs[:10]
