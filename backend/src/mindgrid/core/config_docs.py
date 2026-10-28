"""Render docs/config-reference.md from the Settings classes, so the list of variables
cannot drift from the code that reads them (tools/config_reference.py writes it; a test
fails when it is stale)."""

import inspect

import annotated_types
from pydantic import AliasChoices, SecretStr
from pydantic.fields import FieldInfo

from mindgrid.core.config import AppSettings

HEADER = """# Configuration reference

Generated from the Settings classes by `tools/config_reference.py`; do not edit by hand.
A blank value means the default; a malformed value stops the boot with the variable named.
"""


def render(classes: list[type[AppSettings]]) -> str:
    parts = [HEADER]
    for cls in sorted(classes, key=lambda c: (c.__module__, c.__name__)):
        module = inspect.getmodule(cls)
        summary = (inspect.getdoc(module) or "").splitlines()[0] if module else ""
        parts.append(f"\n## {cls.__name__} (`{cls.__module__}`)\n\n{summary}\n")
        parts.append("\n| Variable | Type | Default | Description |\n|---|---|---|---|\n")
        parts += [_row(field) for field in cls.model_fields.values()]
    return "".join(parts)


def fields(cls: type[AppSettings]) -> list[tuple[str, FieldInfo]]:
    """(primary variable name, field) of every setting, in declaration order."""
    out: list[tuple[str, FieldInfo]] = []
    for field in cls.model_fields.values():
        alias = field.validation_alias
        name = str(alias.choices[0]) if isinstance(alias, AliasChoices) else str(alias)
        out.append((name, field))
    return out


def _row(field: FieldInfo) -> str:
    alias = field.validation_alias
    names = [str(n) for n in alias.choices] if isinstance(alias, AliasChoices) else [str(alias)]
    variable = f"`{names[0]}`" + "".join(f" (legacy `{n}`)" for n in names[1:])
    return f"| {variable} | {_type(field)} | {_default(field)} | {field.description} |\n"


def _type(field: FieldInfo) -> str:
    text = str(field.annotation)
    if "SecretStr" in text:
        return "secret"
    if "tuple" in text:
        return "comma list"
    if "Literal" in text:
        return text.replace("typing.", "")
    name = getattr(field.annotation, "__name__", text)
    for meta in field.metadata:
        if isinstance(meta, annotated_types.Gt):
            name += f" > {meta.gt}"
        elif isinstance(meta, annotated_types.Ge):
            name += f" ≥ {meta.ge}"
    return name


def _default(field: FieldInfo) -> str:
    value = field.default
    if isinstance(value, SecretStr):
        value = value.get_secret_value()
    if value in ("", (), None):
        return "—"
    shown = str(value).lower() if isinstance(value, bool) else str(value)
    return f"`{shown}`"
