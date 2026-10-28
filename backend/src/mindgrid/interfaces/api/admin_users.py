"""/v1/admin/users (superadmin only): every user, create, disable, change system role."""

import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from mindgrid.core.errors import ApiError
from mindgrid.platform.audit import log as audit
from mindgrid.platform.identity import groups, passwords, sessions, users
from mindgrid.platform.identity.models import SystemRole, User, UserGroup, UserStatus

from .deps import SuperadminPrincipal, Tx

router = APIRouter(prefix="/admin/users", tags=["admin"])


class GroupRef(BaseModel):
    id: uuid.UUID
    name: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    system_role: SystemRole
    status: UserStatus
    last_login_at: datetime | None
    avatar: str = ""
    groups: list[GroupRef] = Field(default_factory=list[GroupRef])

    @classmethod
    def of(cls, u: User, in_groups: list[UserGroup] | None = None) -> UserOut:
        return cls(
            id=u.id,
            email=u.email,
            display_name=u.display_name,
            system_role=u.system_role,
            status=u.status,
            last_login_at=u.last_login_at,
            avatar=u.avatar,
            groups=[GroupRef(id=g.id, name=g.name) for g in in_groups or []],
        )


class NewUser(BaseModel):
    email: EmailStr
    display_name: str = Field(default="", max_length=120)
    password: str = Field(min_length=passwords.MIN_LENGTH, max_length=passwords.MAX_LENGTH)
    system_role: SystemRole = SystemRole.USER
    group_ids: list[uuid.UUID] = Field(
        default_factory=list[uuid.UUID], description="Groups to join (their rights apply)."
    )


class PasswordReset(BaseModel):
    password: str = Field(min_length=1, max_length=passwords.MAX_LENGTH)


class UserPatch(BaseModel):
    status: UserStatus | None = None
    system_role: SystemRole | None = None


@router.get("")
async def list_users(_: SuperadminPrincipal, tx: Tx) -> list[UserOut]:
    found = list(await tx.scalars(select(User).order_by(User.created_at)))
    in_groups = await groups.groups_of(tx, [u.id for u in found])
    return [UserOut.of(u, in_groups.get(u.id)) for u in found]


@router.post("", status_code=201)
async def create_user(body: NewUser, principal: SuperadminPrincipal, tx: Tx) -> UserOut:
    user = await users.create_user(
        tx,
        email=str(body.email),
        display_name=body.display_name,
        password=body.password,
        system_role=body.system_role,
    )
    await audit.record(
        tx,
        "user.create",
        target=audit.Target("user", user.id),
        details={"system_role": user.system_role.value},
    )
    await groups.set_groups_of(tx, user.id, set(body.group_ids), principal.superadmin)
    return UserOut.of(user, (await groups.groups_of(tx, [user.id]))[user.id])


@router.patch("/{user_id}")
async def update_user(
    user_id: uuid.UUID, body: UserPatch, principal: SuperadminPrincipal, tx: Tx
) -> UserOut:
    user = await users.get_user(tx, user_id)
    if user is None:
        raise ApiError(404, "user.not_found", "user not found")
    if user_id == principal.user_id and body.model_dump(exclude_none=True):
        raise ApiError(
            400, "user.self_change", "change your own role or status from another account"
        )
    if body.status is not None:
        user.status = body.status
        if body.status == UserStatus.DISABLED:
            await sessions.revoke_all(tx, user_id)
    if body.system_role is not None:
        user.system_role = body.system_role
    await tx.flush()
    await audit.record(
        tx,
        "user.update",
        target=audit.Target("user", user_id),
        details=body.model_dump(mode="json", exclude_none=True),
    )
    return UserOut.of(user)


@router.post("/{user_id}/password", status_code=204)
async def reset_password(
    user_id: uuid.UUID, body: PasswordReset, principal: SuperadminPrincipal, tx: Tx
) -> None:
    """Set another account's password; every sign-in of that account ends."""
    if user_id == principal.user_id:
        raise ApiError(400, "user.self_change", "change your own password from your menu")
    user = await users.get_user(tx, user_id)
    if user is None:
        raise ApiError(404, "user.not_found", "user not found")
    await users.set_password(tx, user, body.password)
    await sessions.revoke_all(tx, user_id)
    await audit.record(tx, "user.password_reset", target=audit.Target("user", user_id))
