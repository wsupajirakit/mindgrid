"""What groups get in a project (a role) and in a category (a level), and who ends up with
which rights. The rules mirror the SQL access functions: a person's own role or grant wins;
otherwise the strongest one among their groups."""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.platform.audit import log as audit
from mindgrid.platform.identity.models import User, UserGroup

from . import access
from .models import (
    Category,
    CategoryGrant,
    CategoryGroupGrant,
    Level,
    Project,
    ProjectGroupRole,
    ProjectRole,
    RoleLevel,
)

ROLE_ORDER = list(ProjectRole)  # strongest first, as the database enum is declared


def strongest(roles: list[ProjectRole]) -> ProjectRole | None:
    return min(roles, key=ROLE_ORDER.index) if roles else None


@dataclass(frozen=True, slots=True)
class GroupRole:
    group_id: uuid.UUID
    name: str
    role: ProjectRole


@dataclass(slots=True)
class Person:
    user_id: uuid.UUID
    name: str
    email: str
    avatar: str
    own_role: ProjectRole | None = None  # set for this person (wins over groups)
    via: list[GroupRole] = field(default_factory=list[GroupRole])  # roles from their groups
    owner: bool = False

    @property
    def role(self) -> ProjectRole | None:
        return self.own_role or strongest([g.role for g in self.via])


async def project_groups(tx: AsyncSession, project_id: uuid.UUID) -> list[GroupRole]:
    await access.require_project_view(tx, project_id)
    rows = await tx.execute(
        select(ProjectGroupRole.group_id, UserGroup.name, ProjectGroupRole.role)
        .join(UserGroup, UserGroup.id == ProjectGroupRole.group_id)
        .where(ProjectGroupRole.project_id == project_id)
        .order_by(UserGroup.name)
    )
    return [GroupRole(r[0], r[1], r[2]) for r in rows]


async def set_project_group(
    tx: AsyncSession, project_id: uuid.UUID, group_id: uuid.UUID, role: ProjectRole
) -> None:
    """Every member of the group (also one added later) gets `role` here."""
    await access.require_members_manage(tx, project_id)
    if await tx.get(UserGroup, group_id) is None:
        raise ApiError(404, "group.not_found", "group not found")
    stmt = insert(ProjectGroupRole).values(project_id=project_id, group_id=group_id, role=role)
    await tx.execute(
        stmt.on_conflict_do_update(index_elements=["project_id", "group_id"], set_={"role": role})
    )
    await audit.record(
        tx,
        "group.project_role",
        project_id=project_id,
        target=audit.Target("group", group_id),
        details={"role": role.value},
    )


async def remove_project_group(
    tx: AsyncSession, project_id: uuid.UUID, group_id: uuid.UUID
) -> None:
    await access.require_members_manage(tx, project_id)
    await tx.execute(
        delete(ProjectGroupRole).where(
            ProjectGroupRole.project_id == project_id, ProjectGroupRole.group_id == group_id
        )
    )
    await audit.record(
        tx, "group.project_remove", project_id=project_id, target=audit.Target("group", group_id)
    )


async def people(tx: AsyncSession, project_id: uuid.UUID) -> list[Person]:
    """The owner, the members and everyone a group brings in, each with where their role
    comes from."""
    await access.require_project_view(tx, project_id)
    project = await tx.get(Project, project_id)
    if project is None:
        raise ApiError(404, "project.not_found", "project not found")
    found: dict[uuid.UUID, Person] = {}
    owner = await tx.get(User, project.owner_id)
    if owner is not None:
        found[owner.id] = Person(
            owner.id, owner.display_name, owner.email, owner.avatar, owner=True
        )
    direct = await tx.execute(
        text("select * from mindgrid_project_member_profiles(:p)"), {"p": project_id}
    )
    for m in direct:
        person = found.setdefault(
            m.user_id, Person(m.user_id, m.display_name, m.email, m.avatar or "")
        )
        person.own_role = ProjectRole(m.role)
    grouped = await tx.execute(
        text("select * from mindgrid_project_group_people(:p)"), {"p": project_id}
    )
    for g in grouped:
        person = found.setdefault(
            g.user_id, Person(g.user_id, g.display_name, g.email, g.avatar or "")
        )
        person.via.append(GroupRole(g.group_id, g.group_name, ProjectRole(g.role)))
    return sorted(found.values(), key=lambda p: (not p.owner, p.name.lower()))


@dataclass(frozen=True, slots=True)
class GroupGrant:
    group_id: uuid.UUID
    name: str
    level: Level


@dataclass(frozen=True, slots=True)
class PersonAccess:
    person: Person
    granted: Level  # their own grant (NONE = none)
    via_groups: Level  # the strongest grant among their groups
    level: Level  # what they can do in the category now
    fixed: bool  # owner or a role that manages the project: always MANAGE


@dataclass(frozen=True, slots=True)
class CategoryAccess:
    restricted: bool
    groups: list[GroupGrant]
    people: list[PersonAccess]


async def _project_of(tx: AsyncSession, category_id: uuid.UUID) -> Category:
    category = await tx.get(Category, category_id)
    if category is None:
        raise ApiError(404, "category.not_found", "category not found")
    return category


async def category_access(tx: AsyncSession, category_id: uuid.UUID) -> CategoryAccess:
    """The category's group grants and every person's resulting level (for those who may
    manage the project's members)."""
    category = await _project_of(tx, category_id)
    await access.require_members_manage(tx, category.project_id)
    roles = {r.role: r for r in await tx.scalars(select(RoleLevel))}
    own = {
        g.user_id: Level(g.level)
        for g in await tx.scalars(
            select(CategoryGrant).where(CategoryGrant.category_id == category_id)
        )
    }
    group_rows = await tx.execute(
        select(CategoryGroupGrant.group_id, UserGroup.name, CategoryGroupGrant.level)
        .join(UserGroup, UserGroup.id == CategoryGroupGrant.group_id)
        .where(CategoryGroupGrant.category_id == category_id)
        .order_by(UserGroup.name)
    )
    groups = [GroupGrant(r[0], r[1], Level(r[2])) for r in group_rows]
    by_group = {g.group_id: g.level for g in groups}
    out: list[PersonAccess] = []
    for person in await people(tx, category.project_id):
        role = person.role
        manages = person.owner or bool(role and roles[role].manage_project)
        from_groups = max(
            (by_group.get(g.group_id, Level.NONE) for g in person.via), default=Level.NONE
        )
        granted = own.get(person.user_id, Level.NONE)
        effective_grant = granted if person.user_id in own else from_groups
        if manages:
            level = Level.MANAGE
        elif role is None:
            level = Level.NONE
        elif category.restricted:
            level = effective_grant
        else:
            level = max(Level(roles[role].default_category_level), effective_grant)
        out.append(PersonAccess(person, granted, from_groups, level, manages))
    return CategoryAccess(category.restricted, groups, out)


async def set_category_group(
    tx: AsyncSession, category_id: uuid.UUID, group_id: uuid.UUID, level: Level
) -> None:
    """Give a group a level in a category (NONE removes it)."""
    category = await _project_of(tx, category_id)
    await access.require_members_manage(tx, category.project_id)
    if await tx.get(UserGroup, group_id) is None:
        raise ApiError(404, "group.not_found", "group not found")
    if level == Level.NONE:
        await tx.execute(
            delete(CategoryGroupGrant).where(
                CategoryGroupGrant.category_id == category_id,
                CategoryGroupGrant.group_id == group_id,
            )
        )
    else:
        stmt = insert(CategoryGroupGrant).values(
            category_id=category_id, group_id=group_id, level=int(level)
        )
        await tx.execute(
            stmt.on_conflict_do_update(
                index_elements=["category_id", "group_id"], set_={"level": int(level)}
            )
        )
    await audit.record(
        tx,
        "group.category_grant",
        project_id=category.project_id,
        target=audit.Target("category", category_id),
        details={"group": str(group_id), "level": level.name.lower()},
    )
