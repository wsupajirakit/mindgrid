"""Machine request verification: key -> signature (±window) -> one-time nonce -> token.
Every failure is a 401 with a stable code; the key's owner becomes the actor, never with
superadmin rights, limited to the key's projects."""

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, text
from sqlalchemy.dialects.postgresql import insert

from mindgrid.core.errors import ApiError
from mindgrid.db.session import SYSTEM, Actor, transaction

from . import config as key_config
from . import signing, tokens
from .models import TokenKind, request_nonces
from .rows import KeyRow

TOKEN_SCHEME = "Signed "  # noqa: S105 — the auth scheme name, not a secret


@dataclass(frozen=True, slots=True)
class Caller:
    api_key_id: uuid.UUID
    key_id: str
    owner_user_id: uuid.UUID
    scopes: frozenset[str]
    projects: tuple[uuid.UUID, ...]

    @property
    def actor(self) -> Actor:
        return Actor(user_id=self.owner_user_id, superadmin=False, projects=self.projects)


def _refuse(code: str, message: str) -> ApiError:
    return ApiError(401, code, message, headers={"WWW-Authenticate": 'Signature realm="api"'})


async def _key(key_id: str) -> KeyRow:
    async with transaction(SYSTEM) as tx:
        row = (
            (await tx.execute(text("select * from mindgrid_api_key_lookup(:k)"), {"k": key_id}))
            .mappings()
            .first()
        )
    key = KeyRow.of(row) if row else None
    if key is None or not key.usable():
        raise _refuse("auth.key_invalid", "unknown, revoked, expired or disabled key")
    return key


async def _once(key_id: str, nonce: str, window_s: int) -> None:
    now = datetime.now(UTC)
    async with transaction(SYSTEM) as tx:
        await tx.execute(
            request_nonces.delete().where(
                request_nonces.c.key_id == key_id,
                request_nonces.c.seen_at < now - timedelta(seconds=2 * window_s),
            )
        )
        added = cast(
            "CursorResult[Any]",
            await tx.execute(
                insert(request_nonces)
                .values(key_id=key_id, nonce=nonce, seen_at=now)
                .on_conflict_do_nothing()
            ),
        )
    if added.rowcount != 1:
        raise _refuse("auth.replay", "this signed request was already used")


async def _token_ok(parts: signing.RequestParts, key: KeyRow) -> bool:
    auth = parts.headers.get("authorization", "")
    if not auth.startswith(TOKEN_SCHEME):
        return False
    row = await tokens.lookup(auth.removeprefix(TOKEN_SCHEME))
    return row is not None and row.usable_as(key.id, TokenKind.ACCESS)


async def verify(parts: signing.RequestParts, *, with_token: bool) -> Caller:
    window = key_config.get_settings().signature_skew_s
    try:
        key_id = signing.keyid_of(parts.headers)
        key = await _key(key_id)
        checked = signing.verify(parts, key.public_key, now=int(time.time()), skew_s=window)
    except signing.SignatureError as err:
        raise _refuse("auth.signature_invalid", str(err)) from None
    await _once(key_id, checked.nonce, window)
    if with_token and not await _token_ok(parts, key):
        raise _refuse("auth.token_invalid", "token invalid, expired or revoked")
    return Caller(
        api_key_id=key.id,
        key_id=key_id,
        owner_user_id=key.owner_user_id,
        scopes=key.scopes,
        projects=key.project_ids,
    )
