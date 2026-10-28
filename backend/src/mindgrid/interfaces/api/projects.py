"""/v1/projects: a user's projects (a superadmin sees all) and their members."""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr, Field

from mindgrid.core.errors import ApiError
from mindgrid.platform.audit import log as audit
from mindgrid.platform.tenancy import access, members, projects
from mindgrid.platform.tenancy.models import Project, ProjectMember, ProjectRole
from mindgrid.platform.tenancy.schemas import ProjectInput

from .deps import CurrentPrincipal, Tx

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectOut(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    slug: str
    name: str
    description: str
    archived: bool
    can_manage: bool = Field(default=False, description="The caller may manage it.")

    @classmethod
    def of(cls, p: Project) -> ProjectOut:
        return cls(
            id=p.id,
            owner_id=p.owner_id,
            slug=p.slug,
            name=p.name,
            description=p.description,
            archived=p.archived,
        )


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    archived: bool | None = None


class MemberOut(BaseModel):
    user_id: uuid.UUID
    role: ProjectRole
    email: str = ""
    display_name: str = ""
    avatar: str = ""

    @classmethod
    def of(cls, m: ProjectMember) -> MemberOut:
        return cls(user_id=m.user_id, role=m.role)


class Invite(BaseModel):
    email: EmailStr
    role: ProjectRole


class RoleChange(BaseModel):
    role: ProjectRole


@router.get("")
async def list_projects(tx: Tx, archived: bool = False) -> list[ProjectOut]:
    return [ProjectOut.of(p) for p in await projects.list_projects(tx, include_archived=archived)]


@router.post("", status_code=201)
async def create_project(body: ProjectInput, principal: CurrentPrincipal, tx: Tx) -> ProjectOut:
    return ProjectOut.of(await projects.create_project(tx, principal.user_id, body))


@router.get("/{project_id}")
async def get_project(project_id: uuid.UUID, tx: Tx) -> ProjectOut:
    out = ProjectOut.of(await projects.get_project(tx, project_id))
    out.can_manage = await access.can_manage_project(tx, project_id)
    return out


@router.patch("/{project_id}")
async def update_project(project_id: uuid.UUID, body: ProjectPatch, tx: Tx) -> ProjectOut:
    await access.require_project_manage(tx, project_id)
    project = await projects.get_project(tx, project_id)
    changes = body.model_dump(exclude_none=True)
    for field, value in changes.items():
        setattr(project, field, value)
    await tx.flush()
    await audit.record(
        tx,
        "project.update",
        project_id=project_id,
        target=audit.Target("project", project_id),
        details={"fields": sorted(changes)},
    )
    return ProjectOut.of(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: uuid.UUID, principal: CurrentPrincipal, tx: Tx) -> None:
    project = await projects.get_project(tx, project_id)
    if project.owner_id != principal.user_id and not principal.superadmin:
        raise ApiError(403, "project.owner_only", "only the owner deletes a project")
    await audit.record(
        tx,
        "project.delete",
        project_id=project_id,
        target=audit.Target("project", project_id),
        details={"slug": project.slug},
    )
    await tx.delete(project)


@router.get("/{project_id}/members")
async def list_members(project_id: uuid.UUID, tx: Tx) -> list[MemberOut]:
    profiles = await members.list_profiles(tx, project_id)
    return [
        MemberOut(
            user_id=p.user_id,
            role=p.role,
            email=p.email,
            display_name=p.display_name,
            avatar=p.avatar,
        )
        for p in profiles
    ]


@router.post("/{project_id}/members", status_code=201)
async def invite_member(project_id: uuid.UUID, body: Invite, tx: Tx) -> MemberOut:
    return MemberOut.of(await members.invite_by_email(tx, project_id, body.email, body.role))


@router.put("/{project_id}/members/{user_id}")
async def change_role(
    project_id: uuid.UUID, user_id: uuid.UUID, body: RoleChange, tx: Tx
) -> MemberOut:
    return MemberOut.of(await members.set_member(tx, project_id, user_id, body.role))


@router.delete("/{project_id}/members/{user_id}", status_code=204)
async def remove_member(project_id: uuid.UUID, user_id: uuid.UUID, tx: Tx) -> None:
    await members.remove_member(tx, project_id, user_id)
