"""Projects: any active user creates its own (1 user : many projects)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.platform.audit import log as audit

from . import access
from .models import Project
from .schemas import ProjectInput


async def create_project(tx: AsyncSession, owner_id: uuid.UUID, data: ProjectInput) -> Project:
    taken = await tx.scalar(
        select(Project.id).where(Project.owner_id == owner_id, Project.slug == data.slug)
    )
    if taken is not None:
        raise ApiError(409, "project.slug_taken", "you already have a project with this slug")
    project = Project(owner_id=owner_id, **data.model_dump())
    tx.add(project)
    await tx.flush()
    await audit.record(
        tx,
        "project.create",
        project_id=project.id,
        target=audit.Target("project", project.id),
        details={"slug": project.slug},
    )
    return project


async def list_projects(tx: AsyncSession, *, include_archived: bool = False) -> list[Project]:
    """Everything the actor may see (row-level security filters; a superadmin sees all)."""
    query = select(Project).order_by(Project.created_at)
    if not include_archived:
        query = query.where(Project.archived.is_(False))
    return list((await tx.scalars(query)).all())


async def get_project(tx: AsyncSession, project_id: uuid.UUID) -> Project:
    await access.require_project_view(tx, project_id)
    project = await tx.get(Project, project_id)
    if project is None:
        raise ApiError(404, "project.not_found", "project not found")
    return project
