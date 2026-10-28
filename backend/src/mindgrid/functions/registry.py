"""Every function by id. Built-ins register on import; packs through the
`mindgrid.functions` entry point group (each entry point is a module that registers)."""

import functools
import importlib
import re
from collections.abc import Callable
from importlib.metadata import entry_points
from typing import Any

from .contracts import Args, Function, Output

ID = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){2,}$")
_FUNCTIONS: dict[str, Function] = {}


def register(fn: Function) -> Function:
    if not ID.fullmatch(fn.id):
        raise ValueError(f"function id {fn.id!r} must look like pack.group.name")
    known = _FUNCTIONS.get(fn.id)
    if known is not None and known.run is not fn.run:
        raise ValueError(f"function {fn.id!r} is registered twice")
    _FUNCTIONS[fn.id] = fn
    return fn


def function[A: Args, O: Output](
    fid: str, summary: str, args: type[A], output: type[O], version: int = 1
) -> Callable[[Callable[[A], O]], Callable[[A], O]]:
    """Decorator: register a pure function under `fid`."""

    def wrap(run: Callable[[A], O]) -> Callable[[A], O]:
        register(Function(fid, version, summary, args, output, run))
        return run

    return wrap


@functools.cache
def load() -> None:
    """Import the built-ins and every installed pack (once per process)."""
    importlib.import_module("mindgrid.functions.builtin.table")
    for entry in entry_points(group="mindgrid.functions"):
        importlib.import_module(entry.value)


def get(fid: str) -> Function | None:
    load()
    return _FUNCTIONS.get(fid)


def catalog() -> list[dict[str, Any]]:
    load()
    return [_FUNCTIONS[k].describe() for k in sorted(_FUNCTIONS)]
