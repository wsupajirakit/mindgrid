import uuid

import pytest
from argon2 import PasswordHasher
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from mindgrid.core.errors import ApiError
from mindgrid.db.session import Actor, transaction
from mindgrid.platform.identity import sessions, signin, users
from mindgrid.platform.identity.models import Session, SystemRole, User, UserStatus

pytestmark = [pytest.mark.anyio, pytest.mark.db]
ROOT = Actor(user_id=None, superadmin=True)
PASSWORD = "Correct horse battery 9"


async def _user(email: str, role: SystemRole = SystemRole.USER) -> uuid.UUID:
    async with transaction(ROOT) as tx:
        user = await users.create_user(
            tx, email=email, display_name="", password=PASSWORD, system_role=role
        )
        return user.id


async def test_rows_are_visible_only_to_their_user_or_a_superadmin(db: None) -> None:
    alice, bob = await _user("alice@example.com"), await _user("bob@example.com")
    async with transaction(Actor(user_id=alice)) as tx:
        assert await users.get_user(tx, alice) is not None
        assert await users.get_user(tx, bob) is None
        assert len((await tx.scalars(select(User))).all()) == 1
    async with transaction(ROOT) as tx:
        assert len((await tx.scalars(select(User))).all()) == 2


async def _insert_user_as(actor: Actor) -> None:
    async with transaction(actor) as tx:
        tx.add(User(email="x@example.com", display_name="x", password_hash="x"))
        await tx.flush()


async def test_only_a_superadmin_creates_users(db: None) -> None:
    alice = await _user("alice@example.com")
    with pytest.raises(DBAPIError, match="row-level security"):
        await _insert_user_as(Actor(user_id=alice))


async def test_email_is_unique_case_insensitively_and_not_a_pattern(db: None) -> None:
    await _user("Alice@Example.com")
    with pytest.raises(ApiError) as err:
        await _user("alice@example.COM")
    assert err.value.code == "user.email_taken"
    await _user("al_ce@example.com")  # "_" is a character, not a wildcard


async def test_sign_in_failures_look_the_same(db: None) -> None:
    alice = await _user("alice@example.com")
    codes: list[tuple[int, str]] = []
    for email, password in [
        ("alice@example.com", "wrong password!!"),
        ("nobody@example.org", PASSWORD),
    ]:
        with pytest.raises(ApiError) as err:
            await signin.sign_in(email, password, "ua")
        codes.append((err.value.status, err.value.code))
    async with transaction(ROOT) as tx:
        user = await users.get_user(tx, alice)
        assert user is not None
        user.status = UserStatus.DISABLED
    with pytest.raises(ApiError) as err:
        await signin.sign_in("alice@example.com", PASSWORD, "ua")
    codes.append((err.value.status, err.value.code))
    assert set(codes) == {(401, "auth.bad_credentials")}


async def test_session_lifecycle_and_hashed_storage(db: None) -> None:
    await _user("alice@example.com", SystemRole.SUPERADMIN)
    signed = await signin.sign_in("ALICE@example.com", PASSWORD, "ua")
    assert signed.superadmin
    async with transaction(Actor(user_id=None)) as tx:
        info = await sessions.resolve(tx, signed.token)
    assert info is not None
    assert info.user_id == signed.user_id
    async with transaction(ROOT) as tx:
        stored = (await tx.scalars(select(Session.token_hash))).all()
        assert signed.token not in stored
        assert sessions.token_hash(signed.token) in stored
        await sessions.revoke(tx, info.session_id)
    async with transaction(Actor(user_id=None)) as tx:
        assert await sessions.resolve(tx, signed.token) is None
        assert await sessions.resolve(tx, "not-a-token") is None


async def test_weak_hash_is_upgraded_on_sign_in(db: None) -> None:
    alice = await _user("alice@example.com")
    weak = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash(PASSWORD)
    async with transaction(ROOT) as tx:
        await tx.execute(text("update users set password_hash = :h"), {"h": weak})
    await signin.sign_in("alice@example.com", PASSWORD, "ua")
    async with transaction(ROOT) as tx:
        user = await users.get_user(tx, alice)
        assert user is not None
        assert user.password_hash != weak
