"""Documents follow category rights; a new version replaces the searchable chunks."""

import uuid

import pytest
from sqlalchemy import func, select

from mindgrid.core.errors import ApiError
from mindgrid.db.session import Actor, transaction
from mindgrid.knowledge.library import service as library
from mindgrid.knowledge.library.models import Chunk
from mindgrid.platform.identity import users
from mindgrid.platform.tenancy import categories, members, projects
from mindgrid.platform.tenancy.models import ProjectRole
from mindgrid.platform.tenancy.schemas import CategoryInput, ProjectInput

pytestmark = [pytest.mark.anyio, pytest.mark.db]
ROOT = Actor(None, superadmin=True)


async def _setup() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """alice owns a project with categories open + secret; bob is a viewer."""
    async with transaction(ROOT) as tx:
        ids = [
            (
                await users.create_user(
                    tx, email=f"{n}@example.com", display_name=n, password="Test-pass-1"
                )
            ).id
            for n in ("alice", "bob")
        ]
    alice, bob = ids
    async with transaction(Actor(alice)) as tx:
        pid = (await projects.create_project(tx, alice, ProjectInput(slug="p", name="P"))).id
        open_cat = (
            await categories.create_category(tx, pid, CategoryInput(slug="open", name="O"))
        ).id
        await categories.create_category(
            tx, pid, CategoryInput(slug="hr", name="H", restricted=True)
        )
        await members.set_member(tx, pid, bob, ProjectRole.VIEWER)
    return alice, bob, pid, open_cat


async def test_rights_and_versions(db: None) -> None:
    alice, bob, _pid, cat = await _setup()
    first = library.Upload(filename="notes.md", data=b"# A\none\n# B\ntwo\n")
    async with transaction(Actor(alice)) as tx:
        doc = await library.add_document(tx, cat, first)
        assert await library.count_chunks(tx, doc.id) == 2
    async with transaction(Actor(bob)) as tx:  # viewer: reads, cannot upload
        assert [d.title for d in await library.list_documents(tx, cat)] == ["notes.md"]
        with pytest.raises(ApiError) as err:
            await library.add_document(tx, cat, first)
        assert err.value.code == "category.forbidden"
    async with transaction(Actor(alice)) as tx:
        found = await library.get_document(tx, doc.id, library.Level.EDIT)
        await library.add_version(tx, found, library.Upload(filename="notes.md", data=b"only one"))
        assert await library.count_chunks(tx, doc.id) == 1
        assert found.current_version == 2


async def test_outsiders_see_no_chunks(db: None) -> None:
    alice, _bob, _pid, cat = await _setup()
    async with transaction(Actor(alice)) as tx:
        await library.add_document(tx, cat, library.Upload(filename="a.txt", data=b"secret plan"))
    async with transaction(ROOT) as tx:
        carol = (
            await users.create_user(
                tx, email="carol@example.com", display_name="c", password="Test-pass-1"
            )
        ).id
    async with transaction(Actor(carol)) as tx:
        assert await tx.scalar(select(func.count()).select_from(Chunk)) == 0
