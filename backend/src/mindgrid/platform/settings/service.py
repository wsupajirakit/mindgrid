"""Read and write declared settings. Row-level security decides who may read or change a
scope; this module checks that the key is declared, allowed at that scope and well typed."""

import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core import settings_registry as registry
from mindgrid.core.errors import ApiError
from mindgrid.core.settings_registry import Scope
from mindgrid.platform.audit import log as audit

from .models import SettingValue


@dataclass(frozen=True, slots=True)
class Resolved:
    key: str
    value: Any
    source: Scope | None  # None = the declared default
    doc: str
    schema: dict[str, Any]  # JSON Schema of the declared type (lets a UI pick the control)


def _definition(key: str, scope: Scope) -> registry.Definition:
    definition = registry.get(key)
    if definition is None:
        raise ApiError(404, "setting.unknown", "no such setting", params={"key": key})
    if scope not in definition.scopes:
        raise ApiError(
            400,
            "setting.scope",
            "not settable at this scope",
            params={"key": key, "scope": scope.value},
        )
    return definition


async def put(
    tx: AsyncSession, scope: Scope, scope_id: uuid.UUID | None, key: str, value: object
) -> None:
    definition = _definition(key, scope)
    try:
        clean = definition.adapter.dump_python(definition.validate(value), mode="json")
    except ValidationError:
        raise ApiError(
            400, "setting.invalid", "value does not fit the setting", params={"key": key}
        ) from None
    row = await tx.scalar(
        select(SettingValue).where(
            SettingValue.scope == scope, SettingValue.scope_id == scope_id, SettingValue.key == key
        )
    )
    if row is None:
        tx.add(SettingValue(scope=scope, scope_id=scope_id, key=key, value=clean))
    else:
        row.value = clean
    await tx.flush()
    await audit.record(
        tx,
        "setting.put",
        target=audit.Target(scope.value, scope_id or "system"),
        details={"key": key},
    )


async def clear(tx: AsyncSession, scope: Scope, scope_id: uuid.UUID | None, key: str) -> None:
    _definition(key, scope)
    await tx.execute(
        delete(SettingValue).where(
            SettingValue.scope == scope, SettingValue.scope_id == scope_id, SettingValue.key == key
        )
    )


async def resolve(
    tx: AsyncSession, key: str, chain: list[tuple[Scope, uuid.UUID | None]]
) -> Resolved:
    """The most specific stored value along `chain` (most specific first), else the default."""
    definition = registry.get(key)
    if definition is None:
        raise ApiError(404, "setting.unknown", "no such setting", params={"key": key})
    for scope, scope_id in chain:
        if scope not in definition.scopes:
            continue
        row = await tx.scalar(
            select(SettingValue.value).where(
                SettingValue.scope == scope,
                SettingValue.scope_id == scope_id,
                SettingValue.key == key,
            )
        )
        if row is not None:
            return Resolved(key, row, scope, definition.doc, definition.adapter.json_schema())
    default = definition.adapter.dump_python(definition.default, mode="json")
    return Resolved(key, default, None, definition.doc, definition.adapter.json_schema())


async def resolve_all(
    tx: AsyncSession, scope: Scope, chain: list[tuple[Scope, uuid.UUID | None]]
) -> list[Resolved]:
    """Every setting declared for `scope`, with its effective value along `chain`."""
    keys = [d.key for d in registry.all_definitions() if scope in d.scopes]
    return [await resolve(tx, key, chain) for key in keys]
