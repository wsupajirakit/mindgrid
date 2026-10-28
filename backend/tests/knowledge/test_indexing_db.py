"""Uploading queues indexing; the worker embeds the newest version's chunks into a space
with its own HNSW index; outsiders see no vectors."""

import uuid
from collections.abc import Callable

import pytest
from sqlalchemy import func, select, text

from mindgrid.core.settings_registry import Scope
from mindgrid.db.session import Actor, transaction
from mindgrid.knowledge.index.models import ChunkEmbedding, EmbeddingSpace
from mindgrid.knowledge.library import service as library
from mindgrid.knowledge.library.models import Chunk, Document, DocumentVersion, VersionStatus
from mindgrid.knowledge.recall import service as recall_service
from mindgrid.platform.identity import users
from mindgrid.platform.jobs import worker
from mindgrid.platform.settings import service as settings_service
from mindgrid.platform.tenancy import categories, projects
from mindgrid.platform.tenancy.schemas import CategoryInput, ProjectInput
from mindgrid.providers.embeddings import factory as embedding_factory
from mindgrid.providers.embeddings.base import Embedder, Space
from mindgrid.providers.llm import factory as llm_factory
from mindgrid.providers.llm.base import Prompt, WriterError

pytestmark = [pytest.mark.anyio, pytest.mark.db]
ROOT = Actor(None, superadmin=True)


def _returning(writer: object) -> Callable[..., object]:
    """A stand-in for the writer factory that always builds `writer`."""

    def build(*_args: object, **_kwargs: object) -> object:
        return writer

    return build


@pytest.fixture
def hashing(env: Callable[..., None]) -> None:
    env(MINDGRID_ENV="test", MINDGRID_EMBEDDING_PROVIDER="hashing")


async def _setup() -> tuple[uuid.UUID, uuid.UUID]:
    async with transaction(ROOT) as tx:
        alice = (
            await users.create_user(
                tx, email="a@example.com", display_name="a", password="Test-pass-1"
            )
        ).id
    async with transaction(Actor(alice)) as tx:
        pid = (await projects.create_project(tx, alice, ProjectInput(slug="p", name="P"))).id
        cat = (await categories.create_category(tx, pid, CategoryInput(slug="c", name="C"))).id
    return alice, cat


async def _count(actor: Actor) -> int:
    async with transaction(actor) as tx:
        return int(await tx.scalar(select(func.count()).select_from(ChunkEmbedding)) or 0)


async def test_upload_is_indexed_by_the_worker(db: None, hashing: None) -> None:
    alice, cat = await _setup()
    data = b"# Rates\nyields up\n# Credit\nspreads wide\n"
    async with transaction(Actor(alice)) as tx:
        doc = await library.add_document(tx, cat, library.Upload(filename="m.md", data=data))
    assert await worker.run_until_empty("w1") == 1
    assert await _count(Actor(alice)) == 2
    async with transaction(Actor(alice)) as tx:
        version = await tx.scalar(
            select(DocumentVersion).where(DocumentVersion.document_id == doc.id)
        )
        assert version is not None
        assert version.status == VersionStatus.INDEXED
        space = await tx.scalar(select(EmbeddingSpace))
        assert space is not None
        assert space.key == "hashing:bag-of-words@64"
        index = await tx.scalar(
            text(
                "select indexdef from pg_indexes where indexname like 'ix_chunk_embeddings_hnsw_%'"
                " and indexdef like '%hashing:bag-of-words@64%'"
            )
        )
        assert index is not None
        assert "vector(64)" in index
        assert "hnsw" in index
    async with transaction(ROOT) as tx:
        bob = (
            await users.create_user(
                tx, email="b@example.com", display_name="b", password="Test-pass-1"
            )
        ).id
    assert await _count(Actor(bob)) == 0


async def test_superseded_version_is_skipped(db: None, hashing: None) -> None:
    alice, cat = await _setup()
    async with transaction(Actor(alice)) as tx:
        doc = await library.add_document(tx, cat, library.Upload(filename="a.txt", data=b"old"))
        await library.add_version(tx, doc, library.Upload(filename="a.txt", data=b"new text"))
    assert await worker.run_until_empty("w1") == 2
    assert await _count(Actor(alice)) == 1


async def test_a_waiting_version_is_queued_once(db: None, hashing: None) -> None:
    from mindgrid.knowledge.index import service as indexing  # noqa: PLC0415
    from mindgrid.platform.jobs.models import Job  # noqa: PLC0415

    alice, cat = await _setup()
    async with transaction(Actor(alice)) as tx:
        doc = await library.add_document(tx, cat, library.Upload(filename="a.txt", data=b"text"))
        version = await tx.scalar(
            select(DocumentVersion).where(DocumentVersion.document_id == doc.id)
        )
        assert version is not None
        await indexing.enqueue(tx, version)  # already queued by the upload
        assert await tx.scalar(select(func.count()).select_from(Job)) == 1


class _Counting:
    """Hashing embedder that records every text it is asked to embed."""

    def __init__(self, inner: Embedder) -> None:
        self.inner = inner
        self.seen: list[str] = []

    @property
    def space(self) -> Space:
        return self.inner.space

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.seen += texts
        return await self.inner.embed_documents(texts)

    async def embed_query(self, text: str) -> list[float]:
        return await self.inner.embed_query(text)


async def test_unchanged_chunks_reuse_their_vectors(
    db: None, hashing: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    counting = _Counting(embedding_factory.build())

    def build(gemini_key: str = "") -> Embedder:
        del gemini_key
        return counting

    monkeypatch.setattr(embedding_factory, "build", build)
    alice, cat = await _setup()
    first = b"# Rates\nyields up\n# Credit\nspreads wide\n"
    second = b"# Rates\nyields up\n# Credit\nspreads tight\n"
    async with transaction(Actor(alice)) as tx:
        doc = await library.add_document(tx, cat, library.Upload(filename="m.md", data=first))
        await library.add_document(tx, cat, library.Upload(filename="copy.md", data=first))
    assert await worker.run_until_empty("w1") == 2
    assert sorted(counting.seen) == ["Credit\nspreads wide", "Rates\nyields up"]  # copy: 0
    counting.seen.clear()
    async with transaction(Actor(alice)) as tx:
        current = await tx.get(Document, doc.id)
        assert current is not None
        await library.add_version(tx, current, library.Upload(filename="m.md", data=second))
    assert await _count(Actor(alice)) == 3  # copy 2 + the unchanged section kept its vector
    assert await worker.run_until_empty("w1") == 1
    assert counting.seen == ["Credit\nspreads tight"]
    assert await _count(Actor(alice)) == 4


class _ContextWriter:
    name = "fake:context"
    max_prompt_chars = None

    def __init__(self, fail_after: int | None = None) -> None:
        self.calls = 0
        self.fail_after = fail_after

    async def write(self, prompt: Prompt) -> str:
        if self.fail_after is not None and self.calls >= self.fail_after:
            raise WriterError("down")
        self.calls += 1
        assert "<chunk" in prompt.user
        assert "<outline>" in prompt.user
        return f"  Part of the zebra handbook, line {self.calls}.\n"


async def _contexts(actor: Actor, doc_id: uuid.UUID) -> list[str]:
    async with transaction(actor) as tx:
        rows = await tx.scalars(
            select(Chunk.context).where(Chunk.document_id == doc_id).order_by(Chunk.ordinal)
        )
        return list(rows)


async def _set_context(alice: uuid.UUID, cat: uuid.UUID, mode: str) -> None:
    async with transaction(Actor(alice)) as tx:
        await settings_service.put(tx, Scope.CATEGORY, cat, "index.contextualize", mode)


async def test_context_lines_are_written_kept_and_searchable(
    db: None, hashing: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer = _ContextWriter()
    monkeypatch.setattr(llm_factory, "build", _returning(writer))
    counting = _Counting(embedding_factory.build())

    def build(gemini_key: str = "") -> Embedder:
        del gemini_key
        return counting

    monkeypatch.setattr(embedding_factory, "build", build)
    alice, cat = await _setup()
    await _set_context(alice, cat, "local")
    first = b"# Rates\nyields up\n# Credit\nspreads wide\n"
    async with transaction(Actor(alice)) as tx:
        doc = await library.add_document(tx, cat, library.Upload(filename="m.md", data=first))
    assert await worker.run_until_empty("w1") == 1
    lines = await _contexts(Actor(alice), doc.id)
    assert lines == ["Part of the zebra handbook, line 1.", "Part of the zebra handbook, line 2."]
    assert counting.seen[0].startswith("Part of the zebra handbook, line 1.\n\nRates")
    async with transaction(Actor(alice)) as tx:  # the line is searchable by keyword
        found = await recall_service.recall(tx, recall_service.Ask(doc.project_id, "zebra"))
    assert {h.document_id for h in found.hits} == {doc.id}

    counting.seen.clear()
    async with transaction(Actor(alice)) as tx:
        current = await tx.get(Document, doc.id)
        assert current is not None
        second = b"# Rates\nyields up\n# Credit\nspreads tight\n"
        await library.add_version(tx, current, library.Upload(filename="m.md", data=second))
    assert await worker.run_until_empty("w1") == 1
    assert writer.calls == 3  # only the changed chunk got a new line
    assert (await _contexts(Actor(alice), doc.id))[0] == "Part of the zebra handbook, line 1."
    assert counting.seen == ["Part of the zebra handbook, line 3.\n\nCredit\nspreads tight"]

    await _set_context(alice, cat, "off")
    async with transaction(Actor(alice)) as tx:
        current = await tx.get(Document, doc.id)
        assert current is not None
        await library.add_version(tx, current, library.Upload(filename="m.md", data=first))
    assert await worker.run_until_empty("w1") == 1
    assert await _contexts(Actor(alice), doc.id) == ["", ""]


async def test_failing_context_writer_still_indexes(
    db: None, hashing: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(llm_factory, "build", _returning(_ContextWriter(fail_after=1)))
    alice, cat = await _setup()
    await _set_context(alice, cat, "local")
    data = b"# Rates\nyields up\n# Credit\nspreads wide\n"
    async with transaction(Actor(alice)) as tx:
        doc = await library.add_document(tx, cat, library.Upload(filename="m.md", data=data))
    assert await worker.run_until_empty("w1") == 1
    assert await _contexts(Actor(alice), doc.id) == ["Part of the zebra handbook, line 1.", ""]
    assert await _count(Actor(alice)) == 2
