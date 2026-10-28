"""Index one document version: read its chunks, embed them outside any transaction (model
calls are slow), then store the vectors and mark the version indexed. A version replaced
by a newer upload in the meantime is skipped; its chunks are already gone.

A chunk whose exact text (and context line, see context.py) already has a vector in the
same space and project (an unchanged section of a new version, a copied document) reuses
that vector instead of being embedded again."""

import dataclasses
import uuid
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from mindgrid.db.session import Actor, transaction
from mindgrid.platform.events import service as events
from mindgrid.platform.jobs import handlers, queue
from mindgrid.platform.jobs.models import Job, JobStatus
from mindgrid.platform.secrets import service as secrets
from mindgrid.providers import config as provider_config
from mindgrid.providers.embeddings import factory
from mindgrid.providers.embeddings.base import Embedder
from mindgrid.providers.llm import factory as llm_factory

from .. import assist
from ..library.models import Chunk, Document, DocumentVersion, VersionStatus, embed_text
from . import context as chunk_context
from . import events as index_events
from .models import ChunkEmbedding

log = structlog.get_logger(__name__)
KIND = "knowledge.index"
LOOKUP_BATCH = 1000  # hashes per reuse query (well under the driver's parameter limit)


@dataclass(frozen=True, slots=True)
class _Work:
    document_id: uuid.UUID
    version_id: uuid.UUID
    project_id: uuid.UUID
    category_id: uuid.UUID
    chunk_ids: list[uuid.UUID]
    hashes: list[bytes]
    title: str
    headings: list[str]
    bodies: list[str]  # embed_text() of each chunk
    contexts: list[str]  # context line per chunk ("" = none)

    @property
    def texts(self) -> list[str]:
        """What the embedder reads: the context line (if any), then the chunk."""
        return [f"{c}\n\n{b}" if c else b for c, b in zip(self.contexts, self.bodies, strict=True)]

    @property
    def keys(self) -> list[tuple[bytes, str]]:
        return list(zip(self.hashes, self.contexts, strict=True))


async def enqueue(tx: AsyncSession, version: DocumentVersion) -> None:
    """Queue indexing once: a version that already waits or runs is not queued again."""
    waiting = await tx.scalar(
        select(Job.id)
        .where(
            Job.kind == KIND,
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
            Job.payload["version_id"].astext == str(version.id),
        )
        .limit(1)
    )
    if waiting is not None:
        return
    payload = {"version_id": str(version.id), "subject": f"documents/{version.document_id}"}
    job = queue.NewJob(KIND, payload, project_id=version.project_id)
    await queue.enqueue(tx, job)


async def carry_over(tx: AsyncSession, version: DocumentVersion) -> None:
    """Before the previous version's chunks are removed: chunks of the new version with an
    identical text take over their vectors (every space), so unchanged sections stay
    searchable by meaning and the index job does not embed them again."""
    new, old = aliased(Chunk), aliased(Chunk)
    same_text = (
        (old.document_id == new.document_id)
        & (old.content_hash == new.content_hash)
        & (old.version_id != new.version_id)
    )
    picked = (
        select(
            new.id, ChunkEmbedding.space, new.project_id, new.category_id, ChunkEmbedding.embedding
        )
        .select_from(new)
        .join(old, same_text)
        .join(ChunkEmbedding, ChunkEmbedding.chunk_id == old.id)
        .where(new.version_id == version.id)
        .ext(distinct_on(new.id, ChunkEmbedding.space))
    )
    columns = ["chunk_id", "space", "project_id", "category_id", "embedding"]
    await tx.execute(insert(ChunkEmbedding).from_select(columns, picked))
    lines = select(old.context).where(same_text, old.context != "").limit(1).scalar_subquery()
    await tx.execute(
        update(new).where(new.version_id == version.id).values(context=func.coalesce(lines, ""))
    )


async def embedder_for(tx: AsyncSession, project_id: uuid.UUID) -> Embedder:
    key = ""
    if provider_config.get_settings().provider == "gemini":
        key = await secrets.reveal_provider_key(tx, project_id, assist.GEMINI_KEY) or ""
    return factory.build(gemini_key=key)


async def _load(tx: AsyncSession, version_id: uuid.UUID) -> _Work | None:
    version = await tx.get(DocumentVersion, version_id)
    if version is None:
        return None
    doc = await tx.get(Document, version.document_id)
    if doc is None or doc.current_version != version.version:
        return None
    rows = (
        await tx.scalars(
            select(Chunk).where(Chunk.version_id == version_id).order_by(Chunk.ordinal)
        )
    ).all()
    return _Work(
        version.document_id,
        version.id,
        version.project_id,
        version.category_id,
        [c.id for c in rows],
        [c.content_hash for c in rows],
        doc.title,
        [c.heading for c in rows],
        [embed_text(c.heading, c.text) for c in rows],
        [c.context for c in rows],
    )


Key = tuple[bytes, str]  # (content hash, context line): equal key = equal embedder input


async def _known(tx: AsyncSession, work: _Work, space: str) -> dict[Key, list[float]]:
    """Vectors already stored in this space for any of the work's chunk inputs."""
    wanted = sorted(set(work.hashes))
    contexts = set(work.contexts)
    found: dict[Key, list[float]] = {}
    for start in range(0, len(wanted), LOOKUP_BATCH):
        rows = await tx.execute(
            select(Chunk.content_hash, Chunk.context, ChunkEmbedding.embedding)
            .join(ChunkEmbedding, ChunkEmbedding.chunk_id == Chunk.id)
            .where(
                ChunkEmbedding.space == space,
                Chunk.project_id == work.project_id,
                Chunk.content_hash.in_(wanted[start : start + LOOKUP_BATCH]),
            )
            .ext(distinct_on(Chunk.content_hash, Chunk.context))
        )
        found |= {
            (digest, line): [float(x) for x in vector]
            for digest, line, vector in rows
            if line in contexts
        }
    return found


async def _vectors(
    embedder: Embedder, work: _Work, known: dict[Key, list[float]]
) -> list[list[float]]:
    """Embed each new input once (an input repeated inside the document too), reuse the rest."""
    todo = {k: t for k, t in zip(work.keys, work.texts, strict=True) if k not in known}
    fresh = dict(zip(todo, await _embed(embedder, list(todo.values())), strict=True))
    log.info("index.vectors", embedded=len(fresh), reused=len(work.keys) - len(todo))
    return [known.get(k) or fresh[k] for k in work.keys]


async def _contextualized(actor: Actor, work: _Work) -> _Work:
    """Context lines per the index.contextualize setting: written for chunks without one
    when on, removed when off (so the stored vectors match the setting)."""
    async with transaction(actor) as tx:
        mode = await assist.mode_of(
            tx, chunk_context.CONTEXTUALIZE, work.project_id, work.category_id
        )
        try:
            writer = await assist.writer_for(tx, work.project_id, mode)
        except llm_factory.WriterUnavailableError as err:
            log.warning("index.context_unavailable", error=str(err))
            writer = None
    if writer is None:
        lines = [""] * len(work.contexts) if mode == "off" else work.contexts
    else:
        lines = await chunk_context.lines(
            writer, work.title, work.headings, work.bodies, work.contexts
        )
    return dataclasses.replace(work, contexts=lines)


async def _embed(embedder: Embedder, texts: list[str]) -> list[list[float]]:
    size = provider_config.get_settings().batch_size
    vectors: list[list[float]] = []
    for start in range(0, len(texts), size):
        vectors += await embedder.embed_documents(texts[start : start + size])
    if len(vectors) != len(texts):
        raise RuntimeError("the embedder returned a different number of vectors")
    return vectors


async def _store(tx: AsyncSession, work: _Work, space: str, vectors: list[list[float]]) -> None:
    await tx.execute(
        delete(ChunkEmbedding).where(
            ChunkEmbedding.chunk_id.in_(work.chunk_ids), ChunkEmbedding.space == space
        )
    )
    tx.add_all(
        ChunkEmbedding(
            chunk_id=cid,
            space=space,
            project_id=work.project_id,
            category_id=work.category_id,
            embedding=vec,
        )
        for cid, vec in zip(work.chunk_ids, vectors, strict=True)
    )
    await tx.execute(
        update(Chunk),
        [
            {"id": cid, "context": line}
            for cid, line in zip(work.chunk_ids, work.contexts, strict=True)
        ],
    )
    version = await tx.get(DocumentVersion, work.version_id)
    if version is not None:
        version.status = VersionStatus.INDEXED
        version.error = ""
    data = index_events.DocumentIndexed(
        document_id=str(work.document_id),
        version_id=str(work.version_id),
        chunks=len(work.chunk_ids),
        space=space,
        links=events.link(
            f"/v1/documents/{work.document_id}",
            f"/projects/{work.project_id}?tab=knowledge&document={work.document_id}",
        ),
    )
    await events.emit(tx, data, project_id=work.project_id, subject=f"documents/{work.document_id}")


async def index_version(actor: Actor, payload: dict[str, Any]) -> None:
    try:
        version_id = uuid.UUID(str(payload["version_id"]))
    except (KeyError, ValueError) as err:
        raise handlers.PermanentJobError("payload needs a version_id") from err
    async with transaction(actor) as tx:
        work = await _load(tx, version_id)
        if work is None:
            return  # removed or superseded: nothing to index
        embedder = await embedder_for(tx, work.project_id)
        space = embedder.space
    work = await _contextualized(actor, work)  # LLM calls, outside any transaction
    async with transaction(actor) as tx:
        known = await _known(tx, work, space.key)
    vectors = await _vectors(embedder, work, known)
    async with transaction(actor) as tx:
        await tx.execute(
            text("select mindgrid_ensure_embedding_space(:key, :provider, :model, :dims)"),
            {
                "key": space.key,
                "provider": space.provider,
                "model": space.model,
                "dims": space.dims,
            },
        )
        if await _load(tx, version_id) is not None:
            await _store(tx, work, space.key, vectors)


handlers.register(KIND, index_version)
