"""Which projects may run a playbook: the system switch (every project) plus one choice per
project (a project's choice wins). Superadmins set both; a project manager sets the
choice for the projects they manage. A changed choice keeps that project's pinned
version and parameters."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.core.settings_registry import Scope
from mindgrid.platform.tenancy.models import Project

from . import catalog, overrides
from .models import PlaybookOverride


@dataclass(frozen=True, slots=True)
class ProjectChoice:
    project_id: uuid.UUID
    name: str
    enabled: bool  # what runs today: the project's choice, else the system switch
    own_choice: bool  # the project made its own choice (it wins over the system switch)
    can_manage: bool


@dataclass(frozen=True, slots=True)
class Assignments:
    playbook_id: str
    all_projects: bool  # the system switch
    projects: list[ProjectChoice]


async def _rows(tx: AsyncSession, playbook_id: str) -> dict[uuid.UUID | None, PlaybookOverride]:
    query = select(PlaybookOverride).where(PlaybookOverride.playbook_id == playbook_id)
    return {r.scope_id if r.scope == Scope.PROJECT else None: r for r in await tx.scalars(query)}


async def _known(tx: AsyncSession, playbook_id: str) -> None:
    if not any(pid == playbook_id for pid, _ in await catalog.all_specs(tx)):
        raise ApiError(404, "playbook.not_found", "playbook not found")


async def of(tx: AsyncSession, playbook_id: str) -> Assignments:
    """The switch and every project the actor can see (row-level security filters them)."""
    await _known(tx, playbook_id)
    rows = await _rows(tx, playbook_id)
    system = rows.get(None)
    everyone = system.enabled if system is not None else False
    projects = (await tx.scalars(select(Project).order_by(Project.name))).all()
    out: list[ProjectChoice] = []
    for p in projects:
        own = rows.get(p.id)
        manage = await tx.scalar(text("select mindgrid_can_manage_project(:p)"), {"p": p.id})
        out.append(
            ProjectChoice(
                project_id=p.id,
                name=p.name,
                enabled=own.enabled if own is not None else everyone,
                own_choice=own is not None,
                can_manage=bool(manage),
            )
        )
    return Assignments(playbook_id, everyone, out)


async def assign(
    tx: AsyncSession,
    playbook_id: str,
    choices: dict[uuid.UUID, bool],
    all_projects: bool | None,
    superadmin: bool,
) -> None:
    """Set the system switch (superadmin) and each project's choice (its manager)."""
    await _known(tx, playbook_id)
    rows = await _rows(tx, playbook_id)
    if all_projects is not None:
        system = rows.get(None)
        change = overrides.Change(
            all_projects,
            system.version if system is not None else None,
            dict(system.params) if system is not None else {},
        )
        await overrides.put(tx, (Scope.SYSTEM, None), playbook_id, change, superadmin)
    for project_id, enabled in choices.items():
        own = rows.get(project_id)
        change = overrides.Change(
            enabled,
            own.version if own is not None else None,
            dict(own.params) if own is not None else {},
        )
        await overrides.put(tx, (Scope.PROJECT, project_id), playbook_id, change, superadmin)
