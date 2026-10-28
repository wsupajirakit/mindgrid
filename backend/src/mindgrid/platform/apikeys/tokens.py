"""Access + refresh tokens for a verified key. Tokens are random; only their SHA-256 is
stored. A refresh token works once: using it returns a new pair, and using a spent one
again (a sign of theft) revokes the whole family (RFC 9700). Revoking a token ends its
family too (RFC 7009: revoking a refresh token should end the grant's access tokens)."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, text, update

from mindgrid.core.errors import ApiError
from mindgrid.db.session import SYSTEM, Actor, transaction
from mindgrid.platform.audit import log as audit

from . import config as key_config
from .models import ApiToken, TokenKind
from .rows import TokenRow


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _invalid() -> ApiError:
    return ApiError(401, "auth.token_invalid", "token invalid, expired or revoked")


async def issue_pair(
    actor: Actor, api_key_id: uuid.UUID, family: uuid.UUID | None = None
) -> TokenPair:
    cfg = key_config.get_settings()
    now = datetime.now(UTC)
    access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    family = family or uuid.uuid4()
    async with transaction(actor) as tx:
        tx.add_all(
            [
                ApiToken(
                    api_key_id=api_key_id,
                    kind=TokenKind.ACCESS,
                    token_hash=digest(access),
                    family_id=family,
                    expires_at=now + timedelta(seconds=cfg.access_ttl_s),
                ),
                ApiToken(
                    api_key_id=api_key_id,
                    kind=TokenKind.REFRESH,
                    token_hash=digest(refresh),
                    family_id=family,
                    expires_at=now + timedelta(days=cfg.refresh_ttl_days),
                ),
            ]
        )
    return TokenPair(access, refresh, cfg.access_ttl_s)


async def lookup(token: str) -> TokenRow | None:
    async with transaction(SYSTEM) as tx:
        row = (
            (
                await tx.execute(
                    text("select * from mindgrid_api_token_lookup(:h)"), {"h": digest(token)}
                )
            )
            .mappings()
            .first()
        )
    return TokenRow.of(row) if row else None


async def _revoke_family(actor: Actor, family: uuid.UUID) -> None:
    async with transaction(actor) as tx:
        await tx.execute(
            update(ApiToken)
            .where(ApiToken.family_id == family, ApiToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )


async def refresh(actor: Actor, api_key_id: uuid.UUID, refresh_token: str) -> TokenPair:
    row = await lookup(refresh_token)
    if row is None or not row.usable_as(api_key_id, TokenKind.REFRESH):
        raise _invalid()
    async with transaction(actor) as tx:
        spent = cast(
            "CursorResult[Any]",
            await tx.execute(
                update(ApiToken)
                .where(ApiToken.id == row.id, ApiToken.used_at.is_(None))
                .values(used_at=datetime.now(UTC))
            ),
        )
    if spent.rowcount != 1:  # already used once: treat as stolen, end the whole family
        await _revoke_family(actor, row.family_id)
        async with transaction(actor) as tx:
            await audit.record(
                tx, "security.refresh_reuse", target=audit.Target("apikey", api_key_id)
            )
        raise ApiError(401, "auth.refresh_reused", "refresh token reused; sign in again")
    return await issue_pair(actor, api_key_id, family=row.family_id)


async def revoke(actor: Actor, api_key_id: uuid.UUID, token: str) -> None:
    """RFC 7009: answer the same whether or not the token was valid."""
    row = await lookup(token)
    if row is not None and row.api_key_id == api_key_id:
        await _revoke_family(actor, row.family_id)
