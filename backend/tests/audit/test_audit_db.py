"""Audit log: who sees which events, append-only, actor taken from the principal."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from mindgrid.core.errors import ApiError
from mindgrid.db.session import Actor, transaction
from mindgrid.platform.audit import log as audit
from mindgrid.platform.identity import signin, users
from mindgrid.platform.tenancy import projects
from mindgrid.platform.tenancy.schemas import ProjectInput

pytestmark = [pytest.mark.anyio, pytest.mark.db]
ROOT = Actor(None, superadmin=True)
PASSWORD = "Correct horse battery 9"


async def _user(name: str) -> uuid.UUID:
    async with transaction(ROOT) as tx:
        user = await users.create_user(
            tx, email=f"{name}@example.com", display_name=name, password=PASSWORD
        )
        return user.id


async def _actions(actor: Actor) -> list[str]:
    async with transaction(actor) as tx:
        return [e.action for e in await audit.page(tx, project_id=None, before=None, limit=50)]


async def test_events_are_visible_to_owner_and_superadmin_only(db: None) -> None:
    alice, bob = await _user("alice"), await _user("bob")
    async with transaction(Actor(alice)) as tx:
        await projects.create_project(tx, alice, ProjectInput(slug="alpha", name="Alpha"))
    assert "project.create" in await _actions(Actor(alice))
    assert "project.create" not in await _actions(Actor(bob))
    assert "user.create" not in await _actions(Actor(alice))
    root_sees = await _actions(ROOT)
    assert "project.create" in root_sees


async def test_failed_sign_in_is_recorded_for_superadmins_only(db: None) -> None:
    alice = await _user("alice")
    with pytest.raises(ApiError):
        await signin.sign_in("alice@example.com", "wrong password!!", "ua")
    assert "auth.sign_in_failed" not in await _actions(Actor(alice))
    assert "auth.sign_in_failed" in await _actions(ROOT)


async def _write(actor: Actor, sql: str, params: dict[str, object] | None = None) -> None:
    async with transaction(actor) as tx:
        await tx.execute(text(sql), params or {})


async def test_append_only_and_no_forged_actor(db: None) -> None:
    alice, bob = await _user("alice"), await _user("bob")
    async with transaction(Actor(alice)) as tx:
        await audit.record(tx, "test.event")
    with pytest.raises(DBAPIError, match="permission denied"):
        await _write(Actor(alice), "update audit_events set action = 'x.y'")
    with pytest.raises(DBAPIError, match="permission denied"):
        await _write(ROOT, "delete from audit_events")
    forged = (
        "insert into audit_events (actor_user_id, actor_superadmin, action, target_type,"
        " target_id, details, request_id) values (:u, false, 'x.y', '', '', '{}', '')"
    )
    with pytest.raises(DBAPIError, match="row-level security"):
        await _write(Actor(alice), forged, {"u": bob})
