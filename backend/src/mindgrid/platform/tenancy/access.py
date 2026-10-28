"""Access checks for code paths: thin calls to the SQL functions that row-level security
uses too, so the API and the database can never disagree. Something the actor may not see
answers 404 (its existence is not revealed); visible but not allowed answers 403."""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError

from .models import Level


async def _bool(tx: AsyncSession, function: str, target: uuid.UUID) -> bool:
    return bool(await tx.scalar(text(f"select {function}(:t)"), {"t": target}))


async def can_view_project(tx: AsyncSession, project_id: uuid.UUID) -> bool:
    return await _bool(tx, "mindgrid_can_view_project", project_id)


async def require_project_view(tx: AsyncSession, project_id: uuid.UUID) -> None:
    if not await can_view_project(tx, project_id):
        raise ApiError(404, "project.not_found", "project not found")


async def can_manage_project(tx: AsyncSession, project_id: uuid.UUID) -> bool:
    return await _bool(tx, "mindgrid_can_manage_project", project_id)


async def require_project_manage(tx: AsyncSession, project_id: uuid.UUID) -> None:
    await require_project_view(tx, project_id)
    if not await _bool(tx, "mindgrid_can_manage_project", project_id):
        raise ApiError(403, "project.forbidden", "not allowed in this project")


async def require_members_manage(tx: AsyncSession, project_id: uuid.UUID) -> None:
    await require_project_view(tx, project_id)
    if not await _bool(tx, "mindgrid_can_manage_members", project_id):
        raise ApiError(403, "project.forbidden", "not allowed in this project")


async def category_level(tx: AsyncSession, category_id: uuid.UUID) -> Level:
    value = await tx.scalar(text("select mindgrid_category_level(:c)"), {"c": category_id})
    return Level(int(value or 0))


async def require_category(tx: AsyncSession, category_id: uuid.UUID, needed: Level) -> Level:
    level = await category_level(tx, category_id)
    if level == Level.NONE:
        raise ApiError(404, "category.not_found", "category not found")
    if level < needed:
        raise ApiError(
            403,
            "category.forbidden",
            "not allowed in this category",
            params={"needed": needed.name.lower()},
        )
    return level


async def project_of_category(tx: AsyncSession, category_id: uuid.UUID) -> uuid.UUID:
    project_id = await tx.scalar(text("select mindgrid_category_project(:c)"), {"c": category_id})
    if project_id is None:
        raise ApiError(404, "category.not_found", "category not found")
    return project_id
