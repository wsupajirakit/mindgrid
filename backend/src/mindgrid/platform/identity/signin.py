"""Sign-in: one generic failure for unknown email, wrong password or disabled account, and
the same hashing time for all three (no account enumeration)."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text

from mindgrid.core.errors import ApiError
from mindgrid.db.session import SYSTEM, Actor, transaction
from mindgrid.platform.audit import log as audit

from . import passwords, sessions
from .models import SystemRole, User, UserStatus


@dataclass(frozen=True, slots=True)
class SignedIn:
    token: str
    user_id: uuid.UUID
    superadmin: bool

    @property
    def actor(self) -> Actor:
        return Actor(user_id=self.user_id, superadmin=self.superadmin)


async def _failure(email: str) -> ApiError:
    """Record the failed attempt (visible to superadmins only) and build the answer."""
    async with transaction(SYSTEM) as tx:
        await audit.record(tx, "auth.sign_in_failed", details={"email": email.strip().lower()})
    return ApiError(401, "auth.bad_credentials", "email or password is wrong")


async def sign_in(email: str, password: str, user_agent: str) -> SignedIn:
    async with transaction(SYSTEM) as tx:
        found = (
            (await tx.execute(text("select * from mindgrid_auth_lookup(:e)"), {"e": email.strip()}))
            .mappings()
            .first()
        )
    if found is None:
        await passwords.burn_time(password)
        raise await _failure(email)
    if not await passwords.verify(found["password_hash"], password):
        raise await _failure(email)
    if found["status"] != UserStatus.ACTIVE:
        raise await _failure(email)
    actor = Actor(user_id=found["id"], superadmin=found["system_role"] == SystemRole.SUPERADMIN)
    async with transaction(actor) as tx:
        user = await tx.get(User, found["id"])
        if user is None:  # deleted between the two steps
            raise await _failure(email)
        if passwords.needs_rehash(user.password_hash):
            user.password_hash = await passwords.hash_password(password)
        user.last_login_at = datetime.now(UTC)
        token = await sessions.open_session(tx, user.id, user_agent)
        await audit.record(tx, "auth.sign_in", target=audit.Target("user", user.id))
    return SignedIn(token=token, user_id=actor.user_id or user.id, superadmin=actor.superadmin)
