"""Copying categories into another project: documents come with their chunks and vectors
(nothing is embedded again), the playbook choices too; grants stay behind."""

import uuid
from collections.abc import Callable

import pytest
from sqlalchemy import func, select

from mindgrid.core.errors import ApiError
from mindgrid.core.settings_registry import Scope
from mindgrid.db.session import Actor, transaction
from mindgrid.knowledge.index.models import ChunkEmbedding
from mindgrid.knowledge.library import copying
from mindgrid.knowledge.library import service as library
from mindgrid.knowledge.library.models import Chunk, Document
from mindgrid.platform.identity import users
from mindgrid.platform.jobs import worker
from mindgrid.platform.tenancy import categories, projects
from mindgrid.platform.tenancy.models import Category
from mindgrid.platform.tenancy.schemas import CategoryInput, ProjectInput
from mindgrid.playbooks import catalog, overrides

pytestmark = [pytest.mark.anyio, pytest.mark.db]
ROOT = Actor(None, superadmin=True)


@pytest.fixture
def hashing(env: Callable[..., None]) -> None:
    env(MINDGRID_ENV="test", MINDGRID_EMBEDDING_PROVIDER="hashing")


async def _setup() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    async with transaction(ROOT) as tx:
        alice = (
            await users.create_user(
                tx, email="a@example.com", display_name="a", password="Test-pass-1"
            )
        ).id
    async with transaction(Actor(alice)) as tx:
        source = (await projects.create_project(tx, alice, ProjectInput(slug="s", name="S"))).id
        target = (await projects.create_project(tx, alice, ProjectInput(slug="t", name="T"))).id
        cat = (await categories.create_category(tx, source, CategoryInput(slug="c", name="C"))).id
        await categories.create_category(tx, target, CategoryInput(slug="c", name="Taken"))
        data = b"# Rates\nyields up\n# Credit\nspreads wide\n"
        await library.add_document(tx, cat, library.Upload(filename="m.md", data=data))
        change = overrides.Change()
        await overrides.put(tx, (Scope.PROJECT, source), "core.table-screen", change, False)
    await worker.run_until_empty("w1")
    return source, target, cat


async def test_copy_brings_documents_vectors_and_playbooks(db: None, hashing: None) -> None:
    source, target, cat = await _setup()
    async with transaction(ROOT) as tx:
        copied = await copying.copy_categories(tx, source, target, [cat])
        assert await overrides.copy_project(tx, source, target, True) == 1
    assert (copied.categories, copied.documents) == (1, 1)
    async with transaction(ROOT) as tx:
        slugs = (await tx.scalars(select(Category.slug).where(Category.project_id == target))).all()
        assert sorted(slugs) == ["c", "c-2"]  # the taken short name gets a suffix
        doc = await tx.scalar(select(Document).where(Document.project_id == target))
        assert doc is not None
        assert doc.source == "copy"
        chunks = await tx.scalar(select(func.count()).where(Chunk.project_id == target))
        vectors = await tx.scalar(
            select(func.count())
            .select_from(ChunkEmbedding)
            .where(ChunkEmbedding.project_id == target)
        )
        assert (chunks, vectors) == (2, 2)
        effective = await catalog.overrides(tx, target)
        assert effective["core.table-screen"].enabled is True
    assert await worker.run_until_empty("w1") == 0  # nothing queued: no embedding again


async def test_copy_refuses_the_same_project_and_foreign_categories(
    db: None, hashing: None
) -> None:
    source, target, cat = await _setup()
    for args in ((source, source, [cat]), (target, source, [cat])):
        with pytest.raises(ApiError):
            async with transaction(ROOT) as tx:
                await copying.copy_categories(tx, *args)
