"""Server-side sessions with opaque tokens. The browser holds a random token; the database
holds only its SHA-256, so a database leak does not hand out live sessions. Logout and
password changes end sessions on the server."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from . import config as session_config
from .models import Session, SystemRole, UserStatus

TOKEN_BYTES = 32


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class SessionInfo:
    session_id: uuid.UUID
    user_id: uuid.UUID
    superadmin: bool


async def open_session(tx: AsyncSession, user_id: uuid.UUID, user_agent: str) -> str:
    """Create a session for the actor bound to `tx`; returns the token (shown once)."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    ttl = timedelta(hours=session_config.get_settings().ttl_hours)
    tx.add(
        Session(
            user_id=user_id,
            token_hash=token_hash(token),
            expires_at=datetime.now(UTC) + ttl,
            user_agent=user_agent[:200],
        )
    )
    await tx.flush()
    return token


async def resolve(tx: AsyncSession, token: str) -> SessionInfo | None:
    """The live session behind a token, or None (unknown, expired, idle, revoked or the
    user is disabled). Runs before the actor is known, through mindgrid_session_lookup."""
    row = (
        (
            await tx.execute(
                text("select * from mindgrid_session_lookup(:h)"), {"h": token_hash(token)}
            )
        )
        .mappings()
        .first()
    )
    if row is None or row["revoked_at"] is not None or row["status"] != UserStatus.ACTIVE:
        return None
    if row["expires_at"] <= datetime.now(UTC):
        return None
    return SessionInfo(
        session_id=row["session_id"],
        user_id=row["user_id"],
        superadmin=row["system_role"] == SystemRole.SUPERADMIN,
    )


async def is_idle(tx: AsyncSession, session_id: uuid.UUID) -> bool:
    cfg = session_config.get_settings()
    session = await tx.get(Session, session_id)
    if session is None:
        return True
    now = datetime.now(UTC)
    if now - session.last_seen_at > timedelta(minutes=cfg.idle_minutes):
        return True
    if now - session.last_seen_at > timedelta(seconds=cfg.touch_every_s):
        session.last_seen_at = now
    return False


async def revoke(tx: AsyncSession, session_id: uuid.UUID) -> None:
    await tx.execute(
        update(Session).where(Session.id == session_id).values(revoked_at=datetime.now(UTC))
    )


async def revoke_all(tx: AsyncSession, user_id: uuid.UUID, keep: uuid.UUID | None = None) -> None:
    query = update(Session).where(Session.user_id == user_id, Session.revoked_at.is_(None))
    if keep is not None:
        query = query.where(Session.id != keep)
    await tx.execute(query.values(revoked_at=datetime.now(UTC)))
