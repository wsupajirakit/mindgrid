"""User groups. /v1/groups lists them for anyone signed in (to pick one); /v1/admin/groups
manages them (superadmin). Projects give a group a role (/v1/projects/{id}/groups) and
categories a level (/v1/categories/{id}/group-grants); /v1/projects/{id}/people shows who
ends up with which role and why."""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field

from mindgrid.platform.identity import groups
from mindgrid.platform.identity.models import UserGroup
from mindgrid.platform.tenancy import group_access
from mindgrid.platform.tenancy.models import Level, ProjectRole

from .deps import CurrentPrincipal, SuperadminPrincipal, Tx

router = APIRouter(tags=["groups"])


class GroupOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    members: int = Field(description="Members the caller can see.")


class GroupRef(BaseModel):
    id: uuid.UUID
    name: str

    @classmethod
    def of(cls, g: UserGroup) -> GroupRef:
        return cls(id=g.id, name=g.name)


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)


class GroupPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class GroupMemberOut(BaseModel):
    user_id: uuid.UUID
    name: str
    email: str
    avatar: str


class UserGroupsIn(BaseModel):
    group_ids: list[uuid.UUID] = Field(default_factory=list[uuid.UUID])


class RoleIn(BaseModel):
    role: ProjectRole


class LevelIn(BaseModel):
    level: Level  # 0 removes the group's grant


class GroupRoleOut(BaseModel):
    group_id: uuid.UUID
    name: str
    role: ProjectRole


class PersonOut(BaseModel):
    user_id: uuid.UUID
    name: str
    email: str
    avatar: str
    role: ProjectRole | None = Field(description="The role in force (own, else groups).")
    own_role: ProjectRole | None = Field(description="Set for this person (wins).")
    via: list[GroupRoleOut] = Field(description="Roles their groups give.")
    owner: bool


def _group_out(s: groups.GroupSummary) -> GroupOut:
    return GroupOut(
        id=s.group.id, name=s.group.name, description=s.group.description, members=s.members
    )


@router.get("/groups")
async def list_groups(tx: Tx) -> list[GroupOut]:
    return [_group_out(s) for s in await groups.list_groups(tx)]


@router.post("/admin/groups", status_code=201)
async def create_group(body: GroupIn, tx: Tx, principal: SuperadminPrincipal) -> GroupOut:
    group = await groups.create_group(tx, body.name, body.description, principal.superadmin)
    return GroupOut(id=group.id, name=group.name, description=group.description, members=0)


@router.patch("/admin/groups/{group_id}")
async def update_group(
    group_id: uuid.UUID, body: GroupPatch, tx: Tx, principal: SuperadminPrincipal
) -> GroupRef:
    change = (body.name, body.description)
    return GroupRef.of(await groups.update_group(tx, group_id, change, principal.superadmin))


@router.delete("/admin/groups/{group_id}", status_code=204)
async def delete_group(group_id: uuid.UUID, tx: Tx, principal: SuperadminPrincipal) -> None:
    await groups.delete_group(tx, group_id, principal.superadmin)


@router.get("/admin/groups/{group_id}/members")
async def group_members(
    group_id: uuid.UUID, tx: Tx, principal: SuperadminPrincipal
) -> list[GroupMemberOut]:
    del principal
    return [
        GroupMemberOut(user_id=u.id, name=u.display_name, email=u.email, avatar=u.avatar)
        for u in await groups.members(tx, group_id)
    ]


@router.put("/admin/groups/{group_id}/members/{user_id}", status_code=204)
async def add_group_member(
    group_id: uuid.UUID, user_id: uuid.UUID, tx: Tx, principal: SuperadminPrincipal
) -> None:
    await groups.add_member(tx, group_id, user_id, principal.superadmin)


@router.delete("/admin/groups/{group_id}/members/{user_id}", status_code=204)
async def remove_group_member(
    group_id: uuid.UUID, user_id: uuid.UUID, tx: Tx, principal: SuperadminPrincipal
) -> None:
    await groups.remove_member(tx, group_id, user_id, principal.superadmin)


@router.put("/admin/users/{user_id}/groups", status_code=204)
async def set_user_groups(
    user_id: uuid.UUID, body: UserGroupsIn, tx: Tx, principal: SuperadminPrincipal
) -> None:
    """Make these exactly the person's groups (they get each group's rights at once)."""
    await groups.set_groups_of(tx, user_id, set(body.group_ids), principal.superadmin)


@router.get("/projects/{project_id}/groups")
async def project_groups(project_id: uuid.UUID, tx: Tx) -> list[GroupRoleOut]:
    return [
        GroupRoleOut(group_id=g.group_id, name=g.name, role=g.role)
        for g in await group_access.project_groups(tx, project_id)
    ]


@router.put("/projects/{project_id}/groups/{group_id}", status_code=204)
async def set_project_group(
    project_id: uuid.UUID, group_id: uuid.UUID, body: RoleIn, tx: Tx, principal: CurrentPrincipal
) -> None:
    del principal
    await group_access.set_project_group(tx, project_id, group_id, body.role)


@router.delete("/projects/{project_id}/groups/{group_id}", status_code=204)
async def remove_project_group(project_id: uuid.UUID, group_id: uuid.UUID, tx: Tx) -> None:
    await group_access.remove_project_group(tx, project_id, group_id)


@router.get("/projects/{project_id}/people")
async def project_people(project_id: uuid.UUID, tx: Tx) -> list[PersonOut]:
    return [
        PersonOut(
            user_id=p.user_id,
            name=p.name,
            email=p.email,
            avatar=p.avatar,
            role=p.role,
            own_role=p.own_role,
            via=[GroupRoleOut(group_id=g.group_id, name=g.name, role=g.role) for g in p.via],
            owner=p.owner,
        )
        for p in await group_access.people(tx, project_id)
    ]


@router.put("/categories/{category_id}/group-grants/{group_id}", status_code=204)
async def set_category_group(
    category_id: uuid.UUID, group_id: uuid.UUID, body: LevelIn, tx: Tx
) -> None:
    await group_access.set_category_group(tx, category_id, group_id, body.level)
