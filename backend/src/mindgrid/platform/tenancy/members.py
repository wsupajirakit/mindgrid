"""Project members and their roles (owner/admin, or a role with manage_members, decides)."""

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.platform.audit import log as audit

from . import access
from .models import Project, ProjectMember, ProjectRole


async def set_member(
    tx: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID, role: ProjectRole
) -> ProjectMember:
    """Add a member or change its role."""
    await access.require_members_manage(tx, project_id)
    project = await tx.get(Project, project_id)
    if project is not None and project.owner_id == user_id:
        raise ApiError(400, "member.is_owner", "the owner is not a member; it has every right")
    member = await tx.get(ProjectMember, (project_id, user_id))
    if member is None:
        member = ProjectMember(project_id=project_id, user_id=user_id, role=role)
        tx.add(member)
    else:
        member.role = role
    await tx.flush()
    await audit.record(
        tx,
        "member.set",
        project_id=project_id,
        target=audit.Target("user", user_id),
        details={"role": role.value},
    )
    return member


async def remove_member(tx: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
    await access.require_members_manage(tx, project_id)
    await tx.execute(
        delete(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
        )
    )
    await audit.record(
        tx, "member.remove", project_id=project_id, target=audit.Target("user", user_id)
    )


async def list_members(tx: AsyncSession, project_id: uuid.UUID) -> list[ProjectMember]:
    await access.require_project_view(tx, project_id)
    query = select(ProjectMember).where(ProjectMember.project_id == project_id)
    return list((await tx.scalars(query)).all())


async def invite_by_email(
    tx: AsyncSession, project_id: uuid.UUID, email: str, role: ProjectRole
) -> ProjectMember:
    """Add an existing active user by email (the caller must manage members)."""
    await access.require_members_manage(tx, project_id)
    user_id = await tx.scalar(text("select mindgrid_user_id_for_email(:e)"), {"e": email.strip()})
    if user_id is None:
        raise ApiError(404, "user.not_found", "no active user with this email")
    return await set_member(tx, project_id, user_id, role)


@dataclass(frozen=True, slots=True)
class MemberProfile:
    user_id: uuid.UUID
    email: str
    display_name: str
    role: ProjectRole
    avatar: str = ""


async def list_profiles(tx: AsyncSession, project_id: uuid.UUID) -> list[MemberProfile]:
    """Members with their names, for anyone who may see the project."""
    await access.require_project_view(tx, project_id)
    rows = await tx.execute(
        text("select * from mindgrid_project_member_profiles(:p)"), {"p": project_id}
    )
    return [
        MemberProfile(r.user_id, r.email, r.display_name, ProjectRole(r.role), r.avatar)
        for r in rows
    ]
