"""Issuing and revoking API keys (superadmin only; row-level security agrees)."""

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.platform.audit import log as audit

from . import config as key_config
from .models import ApiKey, ApiToken, KeyScope

KEY_PREFIX = "mgk_"


@dataclass(frozen=True, slots=True)
class NewKey:
    owner_user_id: uuid.UUID
    name: str
    scopes: tuple[KeyScope, ...]
    project_ids: tuple[uuid.UUID, ...]
    days: int
    public_key_pem: str = ""  # empty: the server makes the pair and returns the private key


@dataclass(frozen=True, slots=True)
class Issued:
    key: ApiKey
    private_key_pem: str  # shown once; empty when the caller brought its own public key


def _public_raw(pem: str) -> bytes:
    try:
        loaded = serialization.load_pem_public_key(pem.encode())
    except ValueError:
        raise ApiError(400, "apikey.bad_public_key", "not a PEM public key") from None
    if not isinstance(loaded, Ed25519PublicKey):
        raise ApiError(400, "apikey.bad_public_key", "the public key must be Ed25519")
    return loaded.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def _new_pair() -> tuple[str, bytes]:
    private = Ed25519PrivateKey.generate()
    pem = private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    raw = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return pem, raw


async def issue(tx: AsyncSession, spec: NewKey) -> Issued:
    limit = key_config.get_settings().key_max_days
    if not spec.scopes or not 1 <= spec.days <= limit:
        raise ApiError(
            400,
            "apikey.invalid",
            "scopes required; lifetime 1..max days",
            params={"max_days": limit},
        )
    private_pem, raw = (
        ("", _public_raw(spec.public_key_pem)) if spec.public_key_pem else _new_pair()
    )
    key = ApiKey(
        key_id=KEY_PREFIX + secrets.token_urlsafe(16),
        owner_user_id=spec.owner_user_id,
        name=spec.name,
        public_key=raw,
        scopes=[s.value for s in spec.scopes],
        project_ids=list(spec.project_ids),
        expires_at=datetime.now(UTC) + timedelta(days=spec.days),
    )
    tx.add(key)
    await tx.flush()
    await audit.record(
        tx,
        "apikey.issue",
        target=audit.Target("apikey", key.key_id),
        details={"owner": str(spec.owner_user_id), "scopes": key.scopes},
    )
    return Issued(key=key, private_key_pem=private_pem)


async def revoke(tx: AsyncSession, key_uuid: uuid.UUID) -> None:
    """End the key and every token issued for it, immediately."""
    key = await tx.get(ApiKey, key_uuid)
    if key is None:
        raise ApiError(404, "apikey.not_found", "API key not found")
    now = datetime.now(UTC)
    key.revoked_at = now
    await tx.execute(
        update(ApiToken)
        .where(ApiToken.api_key_id == key.id, ApiToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await audit.record(tx, "apikey.revoke", target=audit.Target("apikey", key.key_id))


async def rotate(tx: AsyncSession, key_uuid: uuid.UUID) -> Issued:
    """Replace a key with a new pair (same owner, name, scopes, projects and lifetime) and
    end the old one at once; the new private key is returned once."""
    old = await tx.get(ApiKey, key_uuid)
    if old is None:
        raise ApiError(404, "apikey.not_found", "API key not found")
    if old.revoked_at is not None:
        raise ApiError(409, "apikey.revoked", "a revoked key cannot be rotated")
    limit = key_config.get_settings().key_max_days
    days = min(max((old.expires_at - old.created_at).days, 1), limit)
    spec = NewKey(
        owner_user_id=old.owner_user_id,
        name=old.name,
        scopes=tuple(KeyScope(s) for s in old.scopes),
        project_ids=tuple(old.project_ids),
        days=days,
    )
    issued = await issue(tx, spec)
    await revoke(tx, key_uuid)
    await audit.record(
        tx,
        "apikey.rotate",
        target=audit.Target("apikey", old.key_id),
        details={"replaced_by": issued.key.key_id},
    )
    return issued


async def list_keys(tx: AsyncSession) -> list[ApiKey]:
    return list((await tx.scalars(select(ApiKey).order_by(ApiKey.created_at.desc()))).all())
