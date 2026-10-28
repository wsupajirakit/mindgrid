"""Parameter and input values: type and bounds checks, and the effective parameters
(spec default < project override < request), each checked before a run starts."""

from typing import Any, cast

from .spec import InputSpec, ParamSpec, ValueType

_TYPES: dict[ValueType, tuple[type, ...]] = {
    "number": (int, float),
    "integer": (int,),
    "string": (str,),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
}


def _type_ok(kind: ValueType, value: Any) -> bool:
    if isinstance(value, bool) and kind in {"number", "integer"}:
        return False  # JSON true is not a number
    return isinstance(value, _TYPES[kind])


def _dataset_ok(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value)
    return isinstance(value, dict) and isinstance(cast(dict[str, Any], value).get("dataset"), str)


def check_value(spec: ParamSpec | InputSpec, value: Any) -> list[str]:
    if value is None:
        return []
    if spec.type == "dataset":
        return [] if _dataset_ok(value) else ["must be a dataset name"]
    if not _type_ok(spec.type, value):
        return [f"must be {spec.type}"]
    if isinstance(spec, InputSpec):
        return []
    errors: list[str] = []
    if spec.minimum is not None and value < spec.minimum:
        errors.append(f"below the minimum {spec.minimum}")
    if spec.maximum is not None and value > spec.maximum:
        errors.append(f"above the maximum {spec.maximum}")
    if spec.choices is not None and value not in spec.choices:
        errors.append(f"not one of {spec.choices}")
    return errors


def effective(
    specs: dict[str, ParamSpec], *layers: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Merge layers over the defaults; unknown names and bad values are reported."""
    values = {name: p.default for name, p in specs.items()}
    errors: list[str] = []
    for layer in layers:
        for name, value in layer.items():
            if name not in specs:
                errors.append(f"param {name}: not a parameter of this playbook")
                continue
            values[name] = value
    for name, value in values.items():
        errors += [f"param {name}: {e}" for e in check_value(specs[name], value)]
    return values, errors


def check_inputs(specs: dict[str, InputSpec], given: dict[str, Any]) -> list[str]:
    errors = [f"input {n}: not an input of this playbook" for n in given if n not in specs]
    for name, s in specs.items():
        value = given.get(name, s.default)
        if value is None:
            if s.required:
                errors.append(f"input {name}: required")
            continue
        errors += [f"input {name}: {e}" for e in check_value(s, value)]
    return errors
