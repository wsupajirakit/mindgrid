"""Creating, reading and updating users. Callers pass a transaction bound to the acting
principal; row-level security decides which rows exist for it (a holder may update their
own row, a superadmin any)."""

import re
import uuid
from datetime import UTC, datetime

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError

from . import passwords
from .models import SystemRole, User


def check_password_rules(password: str) -> None:
    """At least MIN_LENGTH characters with a lowercase letter, an uppercase letter and a
    digit (a-z, A-Z, 0-9); symbols are allowed, never required."""
    if len(password) < passwords.MIN_LENGTH:
        raise ApiError(
            400,
            "auth.password_short",
            "password too short",
            params={"min": passwords.MIN_LENGTH},
        )
    if len(password) > passwords.MAX_LENGTH:
        raise ApiError(
            400,
            "auth.password_long",
            "password too long",
            params={"max": passwords.MAX_LENGTH},
        )
    missing = passwords.missing_kinds(password)
    if missing:
        raise ApiError(
            400,
            "auth.password_weak",
            "password needs a lowercase letter, an uppercase letter and a digit",
            params={"missing": ",".join(missing)},
        )


def normalize_email(email: str) -> str:
    """Syntax check + normalised form (no DNS lookup: accounts may be created offline)."""
    try:
        return validate_email(email.strip(), check_deliverability=False).normalized
    except EmailNotValidError:
        raise ApiError(400, "user.email_invalid", "not a valid email address") from None


async def create_user(
    tx: AsyncSession,
    *,
    email: str,
    display_name: str,
    password: str,
    system_role: SystemRole = SystemRole.USER,
) -> User:
    check_password_rules(password)
    clean_email = normalize_email(email)
    same_email = func.lower(User.email) == clean_email.lower()  # exact, no wildcards
    exists = await tx.scalar(select(User.id).where(same_email))
    if exists is not None:
        raise ApiError(409, "user.email_taken", "email already registered")
    user = User(
        email=clean_email,
        display_name=display_name.strip() or clean_email,
        password_hash=await passwords.hash_password(password),
        system_role=system_role,
    )
    tx.add(user)
    await tx.flush()
    return user


async def get_user(tx: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await tx.get(User, user_id)


AVATAR = re.compile(r"^[a-z0-9-]{0,40}$")


async def update_profile(
    tx: AsyncSession, user: User, *, display_name: str | None = None, avatar: str | None = None
) -> User:
    """The account holder's own name and picture (from the built-in set)."""
    if display_name is not None:
        name = display_name.strip()
        if not name or len(name) > 120:
            raise ApiError(400, "user.bad_name", "the name is empty or too long")
        user.display_name = name
    if avatar is not None:
        if not AVATAR.fullmatch(avatar):
            raise ApiError(400, "user.bad_avatar", "unknown picture")
        user.avatar = avatar
    await tx.flush()
    return user


async def set_password(tx: AsyncSession, user: User, password: str) -> None:
    check_password_rules(password)
    user.password_hash = await passwords.hash_password(password)
    user.password_changed_at = datetime.now(UTC)
    await tx.flush()


async def change_password(tx: AsyncSession, user: User, current: str, new: str) -> None:
    """The holder changes their own password: the current one must be right."""
    if not await passwords.verify(user.password_hash, current):
        raise ApiError(400, "auth.bad_password", "the current password is wrong")
    await set_password(tx, user, new)
