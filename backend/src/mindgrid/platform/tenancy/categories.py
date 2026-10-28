"""Categories inside a project and per-category grants."""

import uuid

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.platform.audit import log as audit

from . import access
from .models import Category, CategoryGrant, Level
from .schemas import CategoryInput


async def create_category(tx: AsyncSession, project_id: uuid.UUID, data: CategoryInput) -> Category:
    await access.require_project_manage(tx, project_id)
    taken = await tx.scalar(
        select(Category.id).where(Category.project_id == project_id, Category.slug == data.slug)
    )
    if taken is not None:
        raise ApiError(409, "category.slug_taken", "this project already has that category")
    category = Category(project_id=project_id, **data.model_dump())
    tx.add(category)
    await tx.flush()
    await audit.record(
        tx,
        "category.create",
        project_id=project_id,
        target=audit.Target("category", category.id),
        details={"slug": category.slug, "restricted": category.restricted},
    )
    return category


async def list_categories(tx: AsyncSession, project_id: uuid.UUID) -> list[Category]:
    """Categories of the project the actor may read (row-level security filters)."""
    await access.require_project_view(tx, project_id)
    query = select(Category).where(Category.project_id == project_id).order_by(Category.slug)
    return list((await tx.scalars(query)).all())


async def set_grant(
    tx: AsyncSession, category_id: uuid.UUID, user_id: uuid.UUID, level: Level
) -> None:
    project_id = await _project_of(tx, category_id)
    await access.require_members_manage(tx, project_id)
    await audit.record(
        tx,
        "grant.set",
        project_id=project_id,
        target=audit.Target("category", category_id),
        details={"user": str(user_id), "level": level.name.lower()},
    )
    if level == Level.NONE:
        await tx.execute(
            delete(CategoryGrant).where(
                CategoryGrant.category_id == category_id, CategoryGrant.user_id == user_id
            )
        )
        return
    grant = await tx.get(CategoryGrant, (category_id, user_id))
    if grant is None:
        tx.add(CategoryGrant(category_id=category_id, user_id=user_id, level=int(level)))
    else:
        grant.level = int(level)
    await tx.flush()


async def _project_of(tx: AsyncSession, category_id: uuid.UUID) -> uuid.UUID:
    project_id = await tx.scalar(text("select mindgrid_category_project(:c)"), {"c": category_id})
    if project_id is None:
        raise ApiError(404, "category.not_found", "category not found")
    return project_id
