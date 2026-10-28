"""The playbook catalog: shipped and custom specs, and the overrides that decide, per
project, whether a playbook is on, which version runs and with which parameters
(system override, then project override; the project wins). A playbook is off for a
project until it is added there (or switched on for every project)."""

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.core.settings_registry import Scope

from . import checks, shipped, translations
from .models import CustomPlaybook, PlaybookOverride
from .spec import RUNNABLE, PlaybookSpec, Status


@dataclass(slots=True)
class Effective:
    enabled: bool = False  # off until added to the project or switched on for all
    version: int | None = None
    params: dict[str, Any] = field(default_factory=dict[str, Any])


async def all_specs(tx: AsyncSession) -> dict[tuple[str, int], PlaybookSpec]:
    found = dict(shipped.all_specs())
    for row in (await tx.scalars(select(CustomPlaybook))).all():
        found[(row.id, row.version)] = PlaybookSpec.model_validate(row.spec)
    return found


async def overrides(tx: AsyncSession, project_id: uuid.UUID | None) -> dict[str, Effective]:
    query = select(PlaybookOverride).where(
        or_(
            PlaybookOverride.scope == Scope.SYSTEM,
            (PlaybookOverride.scope == Scope.PROJECT) & (PlaybookOverride.scope_id == project_id),
        )
    )
    rows = sorted((await tx.scalars(query)).all(), key=lambda r: r.scope == Scope.PROJECT)
    out: dict[str, Effective] = {}
    for row in rows:  # system first, project last (wins)
        eff = out.setdefault(row.playbook_id, Effective())
        eff.enabled = row.enabled
        eff.version = row.version if row.version is not None else eff.version
        eff.params = {**eff.params, **row.params}
    return out


def pick(
    specs: dict[tuple[str, int], PlaybookSpec],
    playbook_id: str,
    version: int | None,
    pinned: int | None,
) -> PlaybookSpec:
    """The asked version, else the pinned one, else the newest non-draft runnable one."""
    wanted = version or pinned
    if wanted is not None:
        spec = specs.get((playbook_id, wanted))
        if spec is None:
            raise ApiError(
                404,
                "playbook.not_found",
                "no such playbook version",
                params={"id": playbook_id, "version": wanted},
            )
        return spec
    usable = [
        s
        for (pid, _), s in specs.items()
        if pid == playbook_id and s.status in RUNNABLE - {Status.DRAFT}
    ]
    if not usable:
        raise ApiError(404, "playbook.not_found", "no runnable version", params={"id": playbook_id})
    return max(usable, key=lambda s: s.version)


async def summaries(tx: AsyncSession, project_id: uuid.UUID | None) -> list[dict[str, Any]]:
    specs = await all_specs(tx)
    effective = await overrides(tx, project_id)
    texts = await translations.merged(tx, specs)
    ids = sorted({pid for pid, _ in specs})
    out: list[dict[str, Any]] = []
    for pid in ids:
        versions = sorted((s for (i, _), s in specs.items() if i == pid), key=lambda s: s.version)
        eff = effective.get(pid, Effective())
        newest = versions[-1]
        out.append(
            {
                "id": pid,
                "title": newest.title,
                "summary": newest.summary,
                "versions": [{"version": s.version, "status": s.status.value} for s in versions],
                "enabled": eff.enabled,
                "pinned_version": eff.version,
                "params": eff.params,
                "inputs": sorted(newest.inputs),
                "param_names": sorted(newest.params),
                "functions": [step.fn for step in newest.steps],
                "translations": {
                    locale: t.model_dump() for locale, t in texts.get(pid, {}).items()
                },
            }
        )
    return out


async def add_custom(tx: AsyncSession, spec: PlaybookSpec) -> None:
    found = checks.problems(spec)
    if found:
        raise ApiError(
            400, "playbook.invalid", "the spec has problems", params={"problems": found[:20]}
        )
    if (spec.id, spec.version) in await all_specs(tx):
        raise ApiError(
            409,
            "playbook.version_exists",
            "versions never change; add a new one",
            params={"id": spec.id, "version": spec.version},
        )
    tx.add(
        CustomPlaybook(
            id=spec.id,
            version=spec.version,
            status=spec.status,
            spec=spec.model_dump(mode="json", by_alias=True),
        )
    )
    await tx.flush()
