"""Which scope a settings/secrets route acts on, checked before the database is touched
(row-level security enforces the same rules underneath)."""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.core.settings_registry import Scope
from mindgrid.platform.tenancy import access
from mindgrid.platform.tenancy.models import Level

from .deps import Principal

Chain = list[tuple[Scope, uuid.UUID | None]]


@dataclass(frozen=True, slots=True)
class At:
    """A scope and its id (None for the system scope)."""

    scope: Scope
    id: uuid.UUID | None


async def check(
    tx: AsyncSession, principal: Principal, scope: Scope, scope_id: uuid.UUID | None, *, write: bool
) -> None:
    if scope is Scope.SYSTEM:
        if write and not principal.superadmin:
            raise ApiError(403, "auth.superadmin_only", "superadmin only")
    elif scope is Scope.USER:
        if scope_id != principal.user_id and not principal.superadmin:
            raise ApiError(404, "user.not_found", "user not found")
    elif scope is Scope.PROJECT and scope_id is not None:
        await (access.require_project_manage if write else access.require_project_view)(
            tx, scope_id
        )
    elif scope is Scope.CATEGORY and scope_id is not None:
        await access.require_category(tx, scope_id, Level.MANAGE if write else Level.READ)


async def chain_for(
    tx: AsyncSession, principal: Principal, scope: Scope, scope_id: uuid.UUID | None
) -> Chain:
    """Most specific first, ending with the system scope."""
    if scope is Scope.USER:
        return [(Scope.USER, scope_id or principal.user_id), (Scope.SYSTEM, None)]
    if scope is Scope.PROJECT:
        return [(Scope.PROJECT, scope_id), (Scope.SYSTEM, None)]
    if scope is Scope.CATEGORY and scope_id is not None:
        project_id = await access.project_of_category(tx, scope_id)
        return [(Scope.CATEGORY, scope_id), (Scope.PROJECT, project_id), (Scope.SYSTEM, None)]
    return [(Scope.SYSTEM, None)]
