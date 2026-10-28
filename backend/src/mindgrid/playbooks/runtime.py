"""Run a checked spec: each step's arguments are resolved from inputs, parameters and
earlier steps, the function is called, and its output becomes `$steps.<id>`. The first
failing step stops the run; every step is timed and logged."""

import time
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from mindgrid.functions import registry

from . import refs
from .spec import PlaybookSpec


@dataclass(slots=True)
class StepLog:
    id: str
    fn: str
    ms: float
    ok: bool
    error: str = ""


@dataclass(slots=True)
class Result:
    outputs: dict[str, Any] = field(default_factory=dict[str, Any])
    steps: list[StepLog] = field(default_factory=list[StepLog])
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


def _why(err: Exception) -> str:
    if isinstance(err, ValidationError):
        first = err.errors()[0]
        where = ".".join(str(x) for x in first["loc"])
        return f"invalid argument {where}: {first['msg']}"
    return f"{type(err).__name__}: {err}"[:500]


def execute(spec: PlaybookSpec, inputs: dict[str, Any], params: dict[str, Any]) -> Result:
    declared = {name: inputs.get(name) for name in spec.inputs}  # absent optional = None
    scope: dict[str, Any] = {"inputs": {**inputs, **declared}, "params": params, "steps": {}}
    result = Result()
    for step in spec.steps:
        started = time.perf_counter()
        fn = registry.get(step.fn)
        try:
            if fn is None:
                raise LookupError(f"unknown function {step.fn}")
            out = fn.call(refs.resolve(step.with_, scope))
        except Exception as err:  # any failure ends the run with its reason
            ms = round((time.perf_counter() - started) * 1000, 2)
            result.steps.append(StepLog(step.id, step.fn, ms, False, _why(err)))
            result.error = f"step {step.id} failed: {_why(err)}"
            return result
        scope["steps"][step.id] = out.model_dump(mode="json")
        ms = round((time.perf_counter() - started) * 1000, 2)
        result.steps.append(StepLog(step.id, step.fn, ms, True))
    try:
        result.outputs = refs.resolve(spec.outputs, scope)
    except refs.RefError as err:
        result.error = str(err)
    return result
