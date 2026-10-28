"""User groups (superadmin manages them): a name, a description and who is in it."""

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.platform.audit import log as audit

from .models import User, UserGroup, UserGroupMember


@dataclass(frozen=True, slots=True)
class GroupSummary:
    group: UserGroup
    members: int  # the members the caller can see


def _superadmin_only(superadmin: bool) -> None:
    if not superadmin:
        raise ApiError(403, "auth.superadmin_only", "superadmin only")


async def list_groups(tx: AsyncSession) -> list[GroupSummary]:
    counted = await tx.execute(
        select(UserGroupMember.group_id, func.count()).group_by(UserGroupMember.group_id)
    )
    counts: dict[uuid.UUID, int] = {row[0]: int(row[1]) for row in counted}
    groups = (await tx.scalars(select(UserGroup).order_by(UserGroup.name))).all()
    return [GroupSummary(g, counts.get(g.id, 0)) for g in groups]


async def _get(tx: AsyncSession, group_id: uuid.UUID) -> UserGroup:
    group = await tx.get(UserGroup, group_id)
    if group is None:
        raise ApiError(404, "group.not_found", "group not found")
    return group


async def _name_free(tx: AsyncSession, name: str, other_than: uuid.UUID | None = None) -> None:
    taken = await tx.scalar(
        select(UserGroup.id).where(func.lower(UserGroup.name) == name.strip().lower())
    )
    if taken is not None and taken != other_than:
        raise ApiError(409, "group.name_taken", "a group already has this name")


async def create_group(
    tx: AsyncSession, name: str, description: str, superadmin: bool
) -> UserGroup:
    _superadmin_only(superadmin)
    await _name_free(tx, name)
    group = UserGroup(name=name.strip(), description=description)
    tx.add(group)
    await tx.flush()
    await audit.record(tx, "group.create", target=audit.Target("group", group.id))
    return group


async def update_group(
    tx: AsyncSession, group_id: uuid.UUID, change: tuple[str | None, str | None], superadmin: bool
) -> UserGroup:
    _superadmin_only(superadmin)
    name, description = change
    group = await _get(tx, group_id)
    if name is not None:
        await _name_free(tx, name, group_id)
        group.name = name.strip()
    if description is not None:
        group.description = description
    await tx.flush()
    await audit.record(tx, "group.update", target=audit.Target("group", group_id))
    return group


async def delete_group(tx: AsyncSession, group_id: uuid.UUID, superadmin: bool) -> None:
    """Members keep their own roles; whatever the group gave them ends now."""
    _superadmin_only(superadmin)
    await _get(tx, group_id)
    await tx.execute(delete(UserGroup).where(UserGroup.id == group_id))
    await audit.record(tx, "group.delete", target=audit.Target("group", group_id))


async def members(tx: AsyncSession, group_id: uuid.UUID) -> list[User]:
    await _get(tx, group_id)
    query = (
        select(User)
        .join(UserGroupMember, UserGroupMember.user_id == User.id)
        .where(UserGroupMember.group_id == group_id)
        .order_by(User.display_name)
    )
    return list((await tx.scalars(query)).all())


async def add_member(
    tx: AsyncSession, group_id: uuid.UUID, user_id: uuid.UUID, superadmin: bool
) -> None:
    """The person gets every right the group has, at once."""
    _superadmin_only(superadmin)
    await _get(tx, group_id)
    if await tx.get(User, user_id) is None:
        raise ApiError(404, "user.not_found", "user not found")
    await tx.execute(
        insert(UserGroupMember).values(group_id=group_id, user_id=user_id).on_conflict_do_nothing()
    )
    await audit.record(
        tx,
        "group.member_add",
        target=audit.Target("group", group_id),
        details={"user": str(user_id)},
    )


async def remove_member(
    tx: AsyncSession, group_id: uuid.UUID, user_id: uuid.UUID, superadmin: bool
) -> None:
    _superadmin_only(superadmin)
    await tx.execute(
        delete(UserGroupMember).where(
            UserGroupMember.group_id == group_id, UserGroupMember.user_id == user_id
        )
    )
    await audit.record(
        tx,
        "group.member_remove",
        target=audit.Target("group", group_id),
        details={"user": str(user_id)},
    )


async def groups_of(
    tx: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[UserGroup]]:
    """Each person's groups (as far as the caller can see)."""
    rows = await tx.execute(
        select(UserGroupMember.user_id, UserGroup)
        .join(UserGroup, UserGroup.id == UserGroupMember.group_id)
        .where(UserGroupMember.user_id.in_(user_ids))
        .order_by(UserGroup.name)
    )
    out: dict[uuid.UUID, list[UserGroup]] = {u: [] for u in user_ids}
    for row in rows:
        out[row[0]].append(row[1])
    return out


async def set_groups_of(
    tx: AsyncSession, user_id: uuid.UUID, group_ids: set[uuid.UUID], superadmin: bool
) -> None:
    """Make `group_ids` exactly the person's groups (adds and removes)."""
    _superadmin_only(superadmin)
    current = {g.id for g in (await groups_of(tx, [user_id]))[user_id]}
    for gid in group_ids - current:
        await add_member(tx, gid, user_id, superadmin)
    for gid in current - group_ids:
        await remove_member(tx, gid, user_id, superadmin)
