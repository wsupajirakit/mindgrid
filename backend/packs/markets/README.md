# Markets pack

Multi-timeframe OHLCV screens as engine functions and playbooks: data checks and clock,
flow indicators, per-symbol views, staging (full, short, relaxed), regime and sector flow,
structure-based trade setups, ranking, coiled-spring and conviction scores.

Every threshold is a parameter (`MarketParams`) whose default is the value the source
screen uses, so results can be compared one to one (parity test: `markets_tests/test_parity.py`).
Nothing personal is part of the pack: no portfolio, accounts or position sizes.
