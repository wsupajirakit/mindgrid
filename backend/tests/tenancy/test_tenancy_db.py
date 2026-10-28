"""Projects, members, categories and grants: who sees and changes what."""

import uuid
from collections.abc import Awaitable, Callable

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.db.session import Actor, transaction
from mindgrid.platform.identity import users
from mindgrid.platform.tenancy import access, categories, members, projects
from mindgrid.platform.tenancy.models import Level, ProjectRole
from mindgrid.platform.tenancy.schemas import CategoryInput, ProjectInput

pytestmark = [pytest.mark.anyio, pytest.mark.db]
ROOT = Actor(user_id=None, superadmin=True)


async def _users(*names: str) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    async with transaction(ROOT) as tx:
        for name in names:
            user = await users.create_user(
                tx, email=f"{name}@example.com", display_name=name, password="Test-pass-1"
            )
            ids.append(user.id)
    return ids


async def _project(owner: uuid.UUID) -> uuid.UUID:
    async with transaction(Actor(owner)) as tx:
        return (
            await projects.create_project(tx, owner, ProjectInput(slug="alpha", name="Alpha"))
        ).id


async def _code(actor: Actor, call: Callable[[AsyncSession], Awaitable[object]]) -> str:
    async with transaction(actor) as tx:
        try:
            await call(tx)
        except ApiError as err:
            return f"{err.status} {err.code}"
    return "ok"


async def test_owner_sees_own_projects_others_do_not_superadmin_sees_all(db: None) -> None:
    alice, bob = await _users("alice", "bob")
    pid = await _project(alice)
    async with transaction(Actor(alice)) as tx:
        assert [p.id for p in await projects.list_projects(tx)] == [pid]
    async with transaction(Actor(bob)) as tx:
        assert await projects.list_projects(tx) == []
    assert await _code(Actor(bob), lambda tx: projects.get_project(tx, pid)) == (
        "404 project.not_found"
    )
    async with transaction(ROOT) as tx:
        assert len(await projects.list_projects(tx)) == 1


async def test_roles_give_category_levels_and_restricted_needs_a_grant(db: None) -> None:
    alice, bob, carol = await _users("alice", "bob", "carol")
    pid = await _project(alice)
    async with transaction(Actor(alice)) as tx:
        open_cat = await categories.create_category(
            tx, pid, CategoryInput(slug="markets", name="Markets")
        )
        secret = await categories.create_category(
            tx, pid, CategoryInput(slug="hr", name="HR", restricted=True)
        )
        await members.set_member(tx, pid, bob, ProjectRole.EDITOR)
        await members.set_member(tx, pid, carol, ProjectRole.GUEST)
    async with transaction(Actor(bob)) as tx:
        assert await access.category_level(tx, open_cat.id) == Level.EDIT
        assert await access.category_level(tx, secret.id) == Level.NONE
        assert [c.slug for c in await categories.list_categories(tx, pid)] == ["markets"]
    async with transaction(Actor(carol)) as tx:
        assert await categories.list_categories(tx, pid) == []
    async with transaction(Actor(alice)) as tx:
        await categories.set_grant(tx, secret.id, bob, Level.READ)
    async with transaction(Actor(bob)) as tx:
        assert await access.category_level(tx, secret.id) == Level.READ


async def test_only_owner_or_admin_manage(db: None) -> None:
    alice, bob, dan = await _users("alice", "bob", "dan")
    pid = await _project(alice)
    async with transaction(Actor(alice)) as tx:
        await members.set_member(tx, pid, bob, ProjectRole.EDITOR)
    editor = Actor(bob)
    assert await _code(editor, lambda tx: members.set_member(tx, pid, dan, ProjectRole.VIEWER)) == (
        "403 project.forbidden"
    )
    assert await _code(
        editor, lambda tx: categories.create_category(tx, pid, CategoryInput(slug="x", name="x"))
    ) == ("403 project.forbidden")
    async with transaction(Actor(alice)) as tx:
        await members.set_member(tx, pid, bob, ProjectRole.ADMIN)
    assert (
        await _code(editor, lambda tx: members.set_member(tx, pid, dan, ProjectRole.VIEWER)) == "ok"
    )
    outsider = Actor(dan)
    assert await _code(outsider, lambda tx: members.list_members(tx, pid)) == "ok"  # now a viewer


async def test_owner_cannot_be_added_as_member_and_slugs_are_checked(db: None) -> None:
    (alice,) = await _users("alice")
    pid = await _project(alice)
    owner = Actor(alice)
    assert await _code(
        owner, lambda tx: members.set_member(tx, pid, alice, ProjectRole.VIEWER)
    ) == ("400 member.is_owner")
    with pytest.raises(ValidationError):
        ProjectInput(slug="Bad Slug", name="x")
    again = ProjectInput(slug="alpha", name="Again")
    assert await _code(owner, lambda tx: projects.create_project(tx, alice, again)) == (
        "409 project.slug_taken"
    )
