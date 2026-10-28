"""/v1/admin/api-keys (superadmin): issue, list, rotate, revoke. /v1/me/api-keys: a user's own keys
(read only). The private key is returned once at issue and never stored."""

import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from mindgrid.platform.apikeys import keys
from mindgrid.platform.apikeys.models import ApiKey, KeyScope

from .deps import SuperadminPrincipal, Tx

router = APIRouter(tags=["api keys"])


class KeyOut(BaseModel):
    id: uuid.UUID
    key_id: str
    owner_user_id: uuid.UUID
    name: str
    scopes: list[str]
    project_ids: list[uuid.UUID]
    expires_at: datetime
    revoked_at: datetime | None
    last_used_at: datetime | None

    @classmethod
    def of(cls, k: ApiKey) -> KeyOut:
        return cls(
            id=k.id,
            key_id=k.key_id,
            owner_user_id=k.owner_user_id,
            name=k.name,
            scopes=list(k.scopes),
            project_ids=list(k.project_ids),
            expires_at=k.expires_at,
            revoked_at=k.revoked_at,
            last_used_at=k.last_used_at,
        )


class NewKeyBody(BaseModel):
    owner_user_id: uuid.UUID
    name: str = Field(min_length=1, max_length=120)
    scopes: list[KeyScope] = Field(min_length=1)
    project_ids: list[uuid.UUID] = Field(default_factory=list[uuid.UUID])
    days: int = Field(default=90, ge=1)
    public_key_pem: str = Field(default="", max_length=1000)


class IssuedOut(BaseModel):
    key: KeyOut
    private_key_pem: str  # shown once; store it safely, the server keeps no copy


@router.post("/admin/api-keys", status_code=201)
async def issue_key(body: NewKeyBody, _: SuperadminPrincipal, tx: Tx) -> IssuedOut:
    spec = keys.NewKey(
        owner_user_id=body.owner_user_id,
        name=body.name,
        scopes=tuple(body.scopes),
        project_ids=tuple(body.project_ids),
        days=body.days,
        public_key_pem=body.public_key_pem,
    )
    issued = await keys.issue(tx, spec)
    return IssuedOut(key=KeyOut.of(issued.key), private_key_pem=issued.private_key_pem)


@router.get("/admin/api-keys")
async def list_all(_: SuperadminPrincipal, tx: Tx) -> list[KeyOut]:
    return [KeyOut.of(k) for k in await keys.list_keys(tx)]


@router.post("/admin/api-keys/{key_uuid}/revoke", status_code=204)
async def revoke_key(key_uuid: uuid.UUID, _: SuperadminPrincipal, tx: Tx) -> None:
    await keys.revoke(tx, key_uuid)


@router.post("/admin/api-keys/{key_uuid}/rotate", status_code=201)
async def rotate_key(key_uuid: uuid.UUID, _: SuperadminPrincipal, tx: Tx) -> IssuedOut:
    """A new pair for the same owner, scopes and projects; the old key stops working now."""
    issued = await keys.rotate(tx, key_uuid)
    return IssuedOut(key=KeyOut.of(issued.key), private_key_pem=issued.private_key_pem)


@router.get("/me/api-keys")
async def my_keys(tx: Tx) -> list[KeyOut]:
    return [KeyOut.of(k) for k in await keys.list_keys(tx)]  # row-level security: own keys
