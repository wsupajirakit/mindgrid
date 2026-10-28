# Markets pack (`backend/packs/markets`)

Multi-timeframe market screens as engine functions and playbooks. The pack is a separate
package found through entry points; it imports only the engine's `core` and `functions`
contracts and never holds personal data (no portfolio, accounts, NAV or position sizes —
those are inputs of whoever calls it).

## Data

Eight datasets per project, one per timeframe part: `bars-1w-part1`, `bars-1w-part2`,
`bars-1d-part1` … `bars-1h-part2` (CSV with `# key: value` header lines). The connector
template *Market data service exports* fills them on a schedule; uploading the files
(Data tab or `POST /v1/projects/{id}/datasets/{name}`) works too. Every run records the
dataset versions it read.

## Functions

| Function | Does |
|--|--|
| `markets.screen.run` | the whole screen once per snapshot: per-timeframe as-of and bar clock, universe, flow (CMF 50/20, OBV slope, RVOL, IPI), per-symbol views, staging (full / short / relaxed), coil, levels, regime, sectors, data checks |
| `markets.screen.table` | one row per symbol for table functions (stage, relaxed stage, extension, RS60, flow, coil) |
| `markets.regime.summary` | macro rows, breadth, tripwires, permission code, sectors, checks |
| `markets.setup.rank_short` | names at / just under the pivot with positive 1H flow |
| `markets.setup.coiled_spring` | not-extended names coiling with accumulation, lowest risk first |
| `markets.setup.conviction` | conviction 0–10 (strict or relaxed stage) |

Every threshold is a field of `MarketParams` (universe lists, flow weights, stage bands,
coil windows, regime tripwires, setup ATR multiples, spring gates, conviction weights);
playbooks take overrides in the `overrides` parameter, e.g.
`{"stage": {"rsi_high": 62}, "setup": {"stop_atr": 1.75}}`.

Results are codes, never prose: stages (`TRIGGER`, `SETUP`, `MACRO-WATCH`, `SETUP(loose)`,
`WATCH(loose)`, `REVERSAL`, `FAIL`, `KILL`, `*-S`), permission (`regime.risk_off`,
`regime.transition`, `regime.selective`, `regime.risk_on_candidate`) and data checks
(`data.tz_shift`, `data.cmf_out_of_range`, `data.price_jumps`, …).

## Playbooks

| Playbook | Status | Output |
|--|--|--|
| `markets.uipt-screen` v1 | active | candidates in chosen stages (by RS60), regime, sectors, checks |
| `markets.short-rank` v1 | active | near-pivot names with entry, stop, targets, R:R |
| `markets.high-conviction` v1 | active | names scoring at least `min_score` |
| `markets.coiled-spring` v1 | provisional | springs up to `max_risk` (forward results not yet measured here) |

## Parity

`markets_tests/test_parity.py` runs the source screen and the pack on the same CSV folder and
compares every value (views on all timeframes, stages and flags, coil, levels, regime
metrics and breadth, permission, sectors and their order, near-pivot ranking, springs,
conviction strict and relaxed). Measured 25 Oct 2026 on the 23 Oct export (855 symbols,
4 timeframes): **90,925 values compared, 0 differences**; changing two thresholds in the
pack produces 806 differences, so the comparison is not vacuous. Run it with
`MINDGRID_PARITY_SOURCE_LIB`, `MINDGRID_PARITY_SOURCE_PYTHON` and
`MINDGRID_PARITY_CSV_DIR` set (it is skipped otherwise).

Runtime on that export: the screen takes about 9 s in the worker (one thread).
