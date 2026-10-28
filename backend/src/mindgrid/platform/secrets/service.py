"""Write-only secrets. Callers can store, list (name + hint + dates) and delete; only
server code reads the plaintext (`reveal`), for the request that needs it, and it never
leaves the server or reaches a log."""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.core.settings_registry import Scope
from mindgrid.platform.audit import log as audit

from . import crypto
from .models import SecretValue

NAME = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
MAX_SECRET_CHARS = 8192
HINT_CHARS = 4


@dataclass(frozen=True, slots=True)
class SecretInfo:
    name: str
    hint: str
    updated_at: datetime


def _binding(scope: Scope, scope_id: uuid.UUID | None, name: str) -> str:
    return f"{scope.value}:{scope_id or '-'}:{name}"


def _check(name: str, value: str) -> None:
    if not NAME.fullmatch(name):
        raise ApiError(400, "secret.bad_name", "use a-z, 0-9, '_', '.', '-' (max 64)")
    if not value or len(value) > MAX_SECRET_CHARS:
        raise ApiError(
            400, "secret.bad_value", "empty or too long", params={"max": MAX_SECRET_CHARS}
        )


async def put(
    tx: AsyncSession, scope: Scope, scope_id: uuid.UUID | None, name: str, value: str
) -> SecretInfo:
    _check(name, value)
    sealed = crypto.seal(value, _binding(scope, scope_id, name))
    hint = "…" + value[-HINT_CHARS:] if len(value) > HINT_CHARS * 3 else "…"
    row = await tx.scalar(
        select(SecretValue).where(
            SecretValue.scope == scope, SecretValue.scope_id == scope_id, SecretValue.name == name
        )
    )
    if row is None:
        row = SecretValue(
            scope=scope,
            scope_id=scope_id,
            name=name,
            ciphertext=sealed.ciphertext,
            nonce=sealed.nonce,
            key_version=sealed.version,
            hint=hint,
        )
        tx.add(row)
    else:
        row.ciphertext, row.nonce = sealed.ciphertext, sealed.nonce
        row.key_version, row.hint = sealed.version, hint
    await tx.flush()
    await tx.refresh(row)  # server-set updated_at, loaded while still async
    await audit.record(
        tx,
        "secret.put",
        target=audit.Target(scope.value, scope_id or "system"),
        details={"name": name},
    )
    return SecretInfo(name=row.name, hint=row.hint, updated_at=row.updated_at)


async def list_secrets(
    tx: AsyncSession, scope: Scope, scope_id: uuid.UUID | None
) -> list[SecretInfo]:
    rows = await tx.scalars(
        select(SecretValue)
        .where(SecretValue.scope == scope, SecretValue.scope_id == scope_id)
        .order_by(SecretValue.name)
    )
    return [SecretInfo(name=r.name, hint=r.hint, updated_at=r.updated_at) for r in rows]


async def remove(tx: AsyncSession, scope: Scope, scope_id: uuid.UUID | None, name: str) -> None:
    await tx.execute(
        delete(SecretValue).where(
            SecretValue.scope == scope, SecretValue.scope_id == scope_id, SecretValue.name == name
        )
    )
    await audit.record(
        tx,
        "secret.remove",
        target=audit.Target(scope.value, scope_id or "system"),
        details={"name": name},
    )


async def reveal(
    tx: AsyncSession, scope: Scope, scope_id: uuid.UUID | None, name: str
) -> str | None:
    """Server-side use only (e.g. calling a provider). Never return this to a client."""
    row = await tx.scalar(
        select(SecretValue).where(
            SecretValue.scope == scope, SecretValue.scope_id == scope_id, SecretValue.name == name
        )
    )
    if row is None:
        return None
    sealed = crypto.Sealed(ciphertext=row.ciphertext, nonce=row.nonce, version=row.key_version)
    return crypto.open_sealed(sealed, _binding(scope, scope_id, name))


PROVIDER_PREFIX = "provider."


async def reveal_provider_key(tx: AsyncSession, project_id: uuid.UUID, name: str) -> str | None:
    """A model-provider key for work in a project: the project's own, else the system one.
    Anyone who can view the project may have it used on their behalf (server-side only),
    so only names under `provider.` are reachable this way."""
    if not name.startswith(PROVIDER_PREFIX):
        raise ValueError("only provider keys can be used this way")
    row = (
        (
            await tx.execute(
                text("select * from mindgrid_provider_secret(:project, :name)"),
                {"project": project_id, "name": name},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    sealed = crypto.Sealed(
        ciphertext=row["ciphertext"], nonce=row["nonce"], version=row["key_version"]
    )
    scope = Scope(row["scope"])
    return crypto.open_sealed(sealed, _binding(scope, row["scope_id"], name))
