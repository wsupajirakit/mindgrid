"""/v1/projects/{id}/categories and /v1/categories/{id}: categories and per-user grants."""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field

from mindgrid.platform.tenancy import access, categories, group_access
from mindgrid.platform.tenancy.models import Category, Level
from mindgrid.platform.tenancy.schemas import CategoryInput

from .deps import Tx

router = APIRouter(tags=["categories"])


class CategoryOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    slug: str
    name: str
    description: str
    restricted: bool
    my_level: str

    @classmethod
    def of(cls, c: Category, level: Level) -> CategoryOut:
        return cls(
            id=c.id,
            project_id=c.project_id,
            slug=c.slug,
            name=c.name,
            description=c.description,
            restricted=c.restricted,
            my_level=level.name.lower(),
        )


class CategoryPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    restricted: bool | None = None


class GrantBody(BaseModel):
    level: Level  # 0 removes the grant


@router.get("/projects/{project_id}/categories")
async def list_categories(project_id: uuid.UUID, tx: Tx) -> list[CategoryOut]:
    found = await categories.list_categories(tx, project_id)
    return [CategoryOut.of(c, await access.category_level(tx, c.id)) for c in found]


@router.post("/projects/{project_id}/categories", status_code=201)
async def create_category(project_id: uuid.UUID, body: CategoryInput, tx: Tx) -> CategoryOut:
    category = await categories.create_category(tx, project_id, body)
    return CategoryOut.of(category, await access.category_level(tx, category.id))


@router.get("/categories/{category_id}")
async def get_category(category_id: uuid.UUID, tx: Tx) -> CategoryOut:
    level = await access.require_category(tx, category_id, Level.READ)
    category = await tx.get(Category, category_id)
    assert category is not None  # noqa: S101 — visible per the check above
    return CategoryOut.of(category, level)


@router.patch("/categories/{category_id}")
async def update_category(category_id: uuid.UUID, body: CategoryPatch, tx: Tx) -> CategoryOut:
    level = await access.require_category(tx, category_id, Level.MANAGE)
    category = await tx.get(Category, category_id)
    assert category is not None  # noqa: S101
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(category, field, value)
    await tx.flush()
    return CategoryOut.of(category, level)


@router.put("/categories/{category_id}/grants/{user_id}", status_code=204)
async def set_grant(category_id: uuid.UUID, user_id: uuid.UUID, body: GrantBody, tx: Tx) -> None:
    await categories.set_grant(tx, category_id, user_id, body.level)


class GroupGrantOut(BaseModel):
    group_id: uuid.UUID
    name: str
    level: str


class PersonAccessOut(BaseModel):
    user_id: uuid.UUID
    name: str
    email: str
    avatar: str
    role: str = Field(description='"owner", the role in force, or "" (no access to the project).')
    granted: str = Field(description="This person's own grant (none = no grant; it wins).")
    via_groups: str = Field(description="The strongest grant among their groups.")
    level: str = Field(description="What they can do in the category now.")
    fixed: bool = Field(description="Owner or project manager: always manage, no grant needed.")


class CategoryAccessOut(BaseModel):
    restricted: bool
    groups: list[GroupGrantOut]
    people: list[PersonAccessOut]


@router.get("/categories/{category_id}/access")
async def category_access(category_id: uuid.UUID, tx: Tx) -> CategoryAccessOut:
    """Group grants and who can do what in the category (members managers only)."""
    found = await group_access.category_access(tx, category_id)
    return CategoryAccessOut(
        restricted=found.restricted,
        groups=[
            GroupGrantOut(group_id=g.group_id, name=g.name, level=g.level.name.lower())
            for g in found.groups
        ],
        people=[
            PersonAccessOut(
                user_id=a.person.user_id,
                name=a.person.name,
                email=a.person.email,
                avatar=a.person.avatar,
                role="owner" if a.person.owner else (a.person.role or ""),
                granted=a.granted.name.lower(),
                via_groups=a.via_groups.name.lower(),
                level=a.level.name.lower(),
                fixed=a.fixed,
            )
            for a in found.people
        ],
    )
