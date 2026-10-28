"""Specs, references, parameter checks and the runtime, without a database."""

from typing import Any

import pytest

from mindgrid.functions import registry
from mindgrid.playbooks import checks, refs, runtime, shipped
from mindgrid.playbooks.params import check_inputs, effective
from mindgrid.playbooks.spec import PlaybookSpec

ROWS = [
    {"name": "a", "score": 3},
    {"name": "b", "score": 9},
    {"name": "c", "score": 5},
    {"name": "d"},
]


def _screen() -> PlaybookSpec:
    return shipped.all_specs()[("core.table-screen", 1)]


def test_every_shipped_spec_passes_its_checks() -> None:
    specs = shipped.all_specs()
    assert specs
    for spec in specs.values():
        assert checks.problems(spec) == [], spec.id


def test_screen_runs_and_logs_each_step() -> None:
    spec = _screen()
    params, errors = effective(spec.params, {"minimum": 4, "top_n": 1})
    assert errors == []
    result = runtime.execute(spec, {"rows": ROWS}, params)
    assert result.ok
    assert result.outputs == {"rows": [{"name": "b", "score": 9}], "matched": 2}
    assert [s.id for s in result.steps] == ["kept", "ranked", "top"]


def test_parameter_layers_and_bounds() -> None:
    spec = _screen()
    params, errors = effective(spec.params, {"top_n": 5}, {"top_n": 2, "nope": 1})
    assert params["top_n"] == 2
    assert errors == ["param nope: not a parameter of this playbook"]
    _, bad = effective(spec.params, {"top_n": 0, "minimum": True})
    assert "param top_n: below the minimum 1.0" in bad
    assert "param minimum: must be number" in bad
    assert check_inputs(spec.inputs, {}) == ["input rows: required"]


def test_failing_step_stops_the_run_with_its_reason() -> None:
    spec = _screen()
    params, _ = effective(spec.params)
    result = runtime.execute(spec, {"rows": "not a table"}, params)
    assert not result.ok
    assert result.steps[0].ok is False
    assert "invalid argument rows" in result.error


def _spec(**changes: Any) -> PlaybookSpec:
    base = _screen().model_dump(by_alias=True)
    return PlaybookSpec.model_validate({**base, **changes})


def test_checks_catch_unknown_functions_and_dangling_references() -> None:
    steps = [
        {"id": "a", "fn": "core.table.nope", "with": {"rows": "$inputs.missing"}},
        {"id": "b", "fn": "core.table.top", "with": {"rows": "$steps.later.rows"}},
    ]
    found = checks.problems(_spec(steps=steps, outputs={"x": "$steps.b.rows"}))
    assert any("unknown function core.table.nope" in p for p in found)
    assert any("$inputs.missing" in p for p in found)
    assert any("$steps.later.rows" in p for p in found)


def test_references_resolve_inside_structures_and_escape() -> None:
    scope = {"inputs": {"x": 1}, "params": {"p": [2]}, "steps": {"s": {"v": 3}}}
    value = {"a": ["$inputs.x", {"b": "$steps.s.v"}], "c": "$$literal", "d": "$params.p"}
    assert refs.resolve(value, scope) == {"a": [1, {"b": 3}], "c": "$literal", "d": [2]}
    with pytest.raises(refs.RefError):
        refs.resolve("$nowhere.x", scope)


def test_function_catalog_publishes_schemas() -> None:
    ids = [f["id"] for f in registry.catalog()]
    assert {"core.table.filter", "core.table.sort", "core.table.top"} <= set(ids)
    assert registry.catalog()[0]["args"]["type"] == "object"
