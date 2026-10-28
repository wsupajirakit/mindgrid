"""Write-only secrets per scope: /v1/admin/secrets (system), /v1/projects/{id}/secrets,
/v1/categories/{id}/secrets. Responses carry the name, a short hint and the date —
never the value."""

import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from mindgrid.core.settings_registry import Scope
from mindgrid.platform.secrets import service as secrets
from mindgrid.platform.secrets.service import MAX_SECRET_CHARS, SecretInfo

from . import scopes
from .deps import CurrentPrincipal, Tx

router = APIRouter(tags=["secrets"])


class SecretOut(BaseModel):
    name: str
    hint: str
    updated_at: datetime

    @classmethod
    def of(cls, info: SecretInfo) -> SecretOut:
        return cls(name=info.name, hint=info.hint, updated_at=info.updated_at)


class SecretBody(BaseModel):
    value: str = Field(min_length=1, max_length=MAX_SECRET_CHARS)


def _routes(prefix: str, scope: Scope) -> None:
    """Register list / put / delete for one scope (system uses no id)."""
    path = f"{prefix}/secrets"

    @router.get(path, name=f"list_{scope.value}_secrets")
    async def list_(
        tx: Tx, p: CurrentPrincipal, scope_id: uuid.UUID | None = None
    ) -> list[SecretOut]:
        sid = None if scope is Scope.SYSTEM else scope_id
        await scopes.check(tx, p, scope, sid, write=True)  # only managers see names
        return [SecretOut.of(i) for i in await secrets.list_secrets(tx, scope, sid)]

    @router.put(f"{path}/{{name}}", name=f"put_{scope.value}_secret")
    async def put(
        name: str, body: SecretBody, tx: Tx, p: CurrentPrincipal, scope_id: uuid.UUID | None = None
    ) -> SecretOut:
        sid = None if scope is Scope.SYSTEM else scope_id
        await scopes.check(tx, p, scope, sid, write=True)
        return SecretOut.of(await secrets.put(tx, scope, sid, name, body.value))

    @router.delete(f"{path}/{{name}}", status_code=204, name=f"delete_{scope.value}_secret")
    async def remove(
        name: str, tx: Tx, p: CurrentPrincipal, scope_id: uuid.UUID | None = None
    ) -> None:
        sid = None if scope is Scope.SYSTEM else scope_id
        await scopes.check(tx, p, scope, sid, write=True)
        await secrets.remove(tx, scope, sid, name)


_routes("/admin", Scope.SYSTEM)
_routes("/projects/{scope_id}", Scope.PROJECT)
_routes("/categories/{scope_id}", Scope.CATEGORY)
