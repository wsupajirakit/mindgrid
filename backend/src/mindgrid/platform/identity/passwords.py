"""Password hashing: Argon2id (argon2-cffi defaults = RFC 9106 low-memory profile, above
the OWASP Password Storage minimum). Hashes made with older parameters still verify and
are upgraded on the next successful sign-in."""

import functools
from collections.abc import Callable

import anyio
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_LENGTH = 9
MAX_LENGTH = 256  # bounds the hashing work an attacker can request
# Each kind must appear at least once; any other character (symbols, spaces) is allowed.
REQUIRED_KINDS: dict[str, Callable[[str], bool]] = {
    "lower": str.islower,
    "upper": str.isupper,
    "digit": str.isdigit,
}


def missing_kinds(password: str) -> list[str]:
    """The required kinds of character the password lacks (empty when it has them all)."""
    return [
        kind
        for kind, test in REQUIRED_KINDS.items()
        if not any(test(c) and c.isascii() for c in password)
    ]


@functools.cache
def _hasher() -> PasswordHasher:
    return PasswordHasher()


def _hash(password: str) -> str:
    return _hasher().hash(password)


def _verify(password_hash: str, password: str) -> bool:
    try:
        return _hasher().verify(password_hash, password)
    except VerifyMismatchError, VerificationError, InvalidHashError:
        return False


# Argon2id is slow and memory-hard by design: it runs in a worker thread, never on the
# event loop, so one sign-in does not stall every other request.
async def hash_password(password: str) -> str:
    return await anyio.to_thread.run_sync(_hash, password)


async def verify(password_hash: str, password: str) -> bool:
    return await anyio.to_thread.run_sync(_verify, password_hash, password)


def needs_rehash(password_hash: str) -> bool:
    return _hasher().check_needs_rehash(password_hash)


@functools.cache
def _dummy_hash() -> str:
    return _hash("timing-equaliser-not-a-password")


async def burn_time(password: str) -> None:
    """Spend a real verification's time when the account is unknown (no timing oracle)."""
    await anyio.to_thread.run_sync(lambda: _verify(_dummy_hash(), password))
