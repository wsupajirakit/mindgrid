"""Static checks before a spec is accepted: every function exists, every reference points
at a declared input or parameter or an earlier step, defaults respect their bounds."""

from mindgrid.functions import registry

from . import refs
from .params import check_value
from .spec import PlaybookSpec


def problems(spec: PlaybookSpec) -> list[str]:
    found: list[str] = []
    for name, p in spec.params.items():
        found += [f"param {name}: {e}" for e in check_value(p, p.default)]
    seen: set[str] = set()
    for step in spec.steps:
        if registry.get(step.fn) is None:
            found.append(f"step {step.id}: unknown function {step.fn}")
        found += [f"step {step.id}: {e}" for e in _ref_problems(spec, step.with_, seen)]
        seen.add(step.id)
    found += [f"outputs: {e}" for e in _ref_problems(spec, spec.outputs, seen)]
    return found


def _ref_problems(spec: PlaybookSpec, value: object, earlier: set[str]) -> list[str]:
    out: list[str] = []
    try:
        for parts in refs.walk(value):
            root, name = parts[0], parts[1]
            known = {"inputs": spec.inputs, "params": spec.params}.get(root, earlier)
            if name not in known:
                out.append(f"${'.'.join(parts)} refers to nothing declared before it")
    except refs.RefError as err:
        out.append(str(err))
    return out
