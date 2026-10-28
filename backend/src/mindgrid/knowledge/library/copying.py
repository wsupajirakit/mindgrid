"""Copy categories with their documents into another project (superadmin): each document's
current version comes along with its chunks and their vectors, so nothing is embedded
again. Grants stay behind (the other project has its own people)."""

import uuid
from dataclasses import dataclass

from sqlalchemy import insert, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from mindgrid.core.errors import ApiError
from mindgrid.knowledge.index.models import ChunkEmbedding
from mindgrid.platform.audit import log as audit
from mindgrid.platform.tenancy.models import Category

from .models import Chunk, Document, DocumentVersion


@dataclass(frozen=True, slots=True)
class Copied:
    categories: int
    documents: int


async def _free_slug(tx: AsyncSession, project_id: uuid.UUID, slug: str) -> str:
    taken = set(
        (await tx.scalars(select(Category.slug).where(Category.project_id == project_id))).all()
    )
    candidate, n = slug, 1
    while candidate in taken:
        n += 1
        candidate = f"{slug[:58]}-{n}"
    return candidate


async def _copy_version(
    tx: AsyncSession, source: DocumentVersion, doc: Document, target: Category
) -> None:
    version = DocumentVersion(
        document_id=doc.id,
        project_id=target.project_id,
        category_id=target.id,
        version=1,
        filename=source.filename,
        media_type=source.media_type,
        size_bytes=source.size_bytes,
        sha256=source.sha256,
        blob=source.blob,
        status=source.status,
        error=source.error,
        chunk_count=source.chunk_count,
    )
    tx.add(version)
    await tx.flush()
    await _copy_chunks(tx, source.id, version, target)


_CHUNK_COLUMNS = [
    "document_id",
    "version_id",
    "project_id",
    "category_id",
    "ordinal",
    "heading",
    "text",
    "location",
    "content_hash",
    "context",
]


async def _copy_chunks(
    tx: AsyncSession, source_version: uuid.UUID, version: DocumentVersion, target: Category
) -> None:
    """The chunks, then each new chunk takes the vectors of the one at the same position."""
    chunks = select(
        literal(version.document_id),
        literal(version.id),
        literal(target.project_id),
        literal(target.id),
        Chunk.ordinal,
        Chunk.heading,
        Chunk.text,
        Chunk.location,
        Chunk.content_hash,
        Chunk.context,
    ).where(Chunk.version_id == source_version)
    await tx.execute(insert(Chunk).from_select(_CHUNK_COLUMNS, chunks))
    new, old = aliased(Chunk), aliased(Chunk)
    vectors = (
        select(
            new.id,
            ChunkEmbedding.space,
            literal(target.project_id),
            literal(target.id),
            ChunkEmbedding.embedding,
        )
        .select_from(new)
        .join(old, (old.version_id == source_version) & (old.ordinal == new.ordinal))
        .join(ChunkEmbedding, ChunkEmbedding.chunk_id == old.id)
        .where(new.version_id == version.id)
    )
    await tx.execute(
        insert(ChunkEmbedding).from_select(
            ["chunk_id", "space", "project_id", "category_id", "embedding"], vectors
        )
    )


async def copy_categories(
    tx: AsyncSession,
    source_project: uuid.UUID,
    target_project: uuid.UUID,
    category_ids: list[uuid.UUID],
) -> Copied:
    if source_project == target_project:
        raise ApiError(400, "copy.same_project", "pick another project to copy into")
    documents = 0
    for category_id in category_ids:
        source = await tx.get(Category, category_id)
        if source is None or source.project_id != source_project:
            raise ApiError(404, "category.not_found", "category not found")
        target = Category(
            project_id=target_project,
            slug=await _free_slug(tx, target_project, source.slug),
            name=source.name,
            description=source.description,
            restricted=source.restricted,
        )
        tx.add(target)
        await tx.flush()
        docs = (
            await tx.scalars(
                select(Document).where(
                    Document.category_id == category_id, Document.current_version > 0
                )
            )
        ).all()
        for d in docs:
            version = await tx.scalar(
                select(DocumentVersion).where(
                    DocumentVersion.document_id == d.id,
                    DocumentVersion.version == d.current_version,
                )
            )
            if version is None:
                continue
            doc = Document(
                project_id=target_project,
                category_id=target.id,
                title=d.title,
                trust=d.trust,
                source="copy",
                current_version=1,
            )
            tx.add(doc)
            await tx.flush()
            await _copy_version(tx, version, doc, target)
            documents += 1
        await audit.record(
            tx,
            "category.copy",
            project_id=target_project,
            target=audit.Target("category", target.id),
            details={"from": str(category_id), "documents": len(docs)},
        )
    return Copied(len(category_ids), documents)
