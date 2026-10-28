"""Set or clear an override. System overrides need a superadmin, project overrides a
project manager (row-level security enforces the same)."""

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.core.settings_registry import Scope
from mindgrid.platform.audit import log as audit
from mindgrid.platform.tenancy import access

from . import catalog
from .models import PlaybookOverride
from .params import effective


@dataclass(frozen=True, slots=True)
class Change:
    enabled: bool = True
    version: int | None = None
    params: dict[str, Any] = field(default_factory=dict[str, Any])


async def _allowed(
    tx: AsyncSession, scope: Scope, scope_id: uuid.UUID | None, superadmin: bool
) -> None:
    if scope is Scope.SYSTEM and not superadmin:
        raise ApiError(403, "auth.superadmin_only", "superadmin only")
    if scope is Scope.PROJECT and scope_id is not None:
        await access.require_project_manage(tx, scope_id)
    if scope not in {Scope.SYSTEM, Scope.PROJECT}:
        raise ApiError(400, "playbook.bad_scope", "overrides are per system or project")


async def put(
    tx: AsyncSession,
    target: tuple[Scope, uuid.UUID | None],
    playbook_id: str,
    change: Change,
    superadmin: bool,
) -> None:
    scope, scope_id = target
    await _allowed(tx, scope, scope_id, superadmin)
    specs = await catalog.all_specs(tx)
    spec = catalog.pick(specs, playbook_id, change.version, None)
    _, errors = effective(spec.params, change.params)
    if errors:
        raise ApiError(400, "playbook.param_invalid", "bad parameter", params={"problems": errors})
    row = await tx.scalar(
        select(PlaybookOverride).where(
            PlaybookOverride.scope == scope,
            PlaybookOverride.scope_id == scope_id,
            PlaybookOverride.playbook_id == playbook_id,
        )
    )
    if row is None:
        row = PlaybookOverride(scope=scope, scope_id=scope_id, playbook_id=playbook_id)
        tx.add(row)
    row.enabled, row.version, row.params = change.enabled, change.version, change.params
    await tx.flush()
    await audit.record(
        tx,
        "playbook.override",
        project_id=scope_id,
        target=audit.Target("playbook", playbook_id),
        details={"enabled": change.enabled, "version": change.version},
    )


async def clear(
    tx: AsyncSession, target: tuple[Scope, uuid.UUID | None], playbook_id: str, superadmin: bool
) -> None:
    scope, scope_id = target
    await _allowed(tx, scope, scope_id, superadmin)
    await tx.execute(
        delete(PlaybookOverride).where(
            PlaybookOverride.scope == scope,
            PlaybookOverride.scope_id == scope_id,
            PlaybookOverride.playbook_id == playbook_id,
        )
    )


async def copy_project(
    tx: AsyncSession, source: uuid.UUID, target: uuid.UUID, superadmin: bool
) -> int:
    """Give `target` the same playbook choices as `source` (on/off, version, parameters)."""
    rows = (
        await tx.scalars(
            select(PlaybookOverride).where(
                PlaybookOverride.scope == Scope.PROJECT, PlaybookOverride.scope_id == source
            )
        )
    ).all()
    for row in rows:
        change = Change(row.enabled, row.version, dict(row.params))
        await put(tx, (Scope.PROJECT, target), row.playbook_id, change, superadmin)
    return len(rows)
