"""Documents and versions: upload -> parse -> clean -> chunk -> store. Each upload of the
same document is a new version; the newest one is what search sees. Indexing (embedding)
runs after this, in the background."""

import hashlib
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.knowledge.index import service as indexing
from mindgrid.knowledge.intake import chunking, parsers
from mindgrid.knowledge.intake import config as intake_config
from mindgrid.platform.audit import log as audit
from mindgrid.platform.tenancy import access
from mindgrid.platform.tenancy.models import Level

from .models import Chunk, Document, DocumentVersion, Trust, VersionStatus, content_hash

__all__ = ["Level", "Upload"]


@dataclass(frozen=True, slots=True)
class Upload:
    filename: str
    data: bytes
    title: str = ""
    trust: Trust = Trust.UNRATED


def _check_size(data: bytes) -> None:
    limit = intake_config.get_settings().max_upload_bytes
    if not data:
        raise ApiError(400, "document.empty", "the file has no content")
    if len(data) > limit:
        raise ApiError(413, "document.too_large", "file too large", params={"max": limit})


async def add_document(tx: AsyncSession, category_id: uuid.UUID, upload: Upload) -> Document:
    await access.require_category(tx, category_id, Level.EDIT)
    project_id = await access.project_of_category(tx, category_id)
    doc = Document(
        project_id=project_id,
        category_id=category_id,
        trust=upload.trust,
        title=(upload.title or upload.filename)[:300],
    )
    tx.add(doc)
    await tx.flush()
    await add_version(tx, doc, upload)
    await audit.record(
        tx,
        "document.create",
        project_id=project_id,
        target=audit.Target("document", doc.id),
        details={"title": doc.title},
    )
    await tx.refresh(doc)  # server-set columns (updated_at) loaded while still async
    return doc


async def add_version(tx: AsyncSession, doc: Document, upload: Upload) -> DocumentVersion:
    _check_size(upload.data)
    media = parsers.media_type(upload.filename)
    sections = parsers.parse(upload.filename, upload.data)
    cfg = intake_config.get_settings()
    pieces = chunking.chunk(sections, cfg.chunk_chars, cfg.chunk_overlap_chars)
    if not pieces:
        raise ApiError(400, "document.empty", "no text could be read from the file")
    doc.current_version += 1
    version = DocumentVersion(
        document_id=doc.id,
        project_id=doc.project_id,
        category_id=doc.category_id,
        version=doc.current_version,
        filename=upload.filename[:255],
        media_type=media,
        size_bytes=len(upload.data),
        sha256=hashlib.sha256(upload.data).hexdigest(),
        blob=upload.data,
        status=VersionStatus.PARSED,
        chunk_count=len(pieces),
    )
    tx.add(version)
    await tx.flush()
    tx.add_all(
        Chunk(
            document_id=doc.id,
            version_id=version.id,
            project_id=doc.project_id,
            category_id=doc.category_id,
            ordinal=i,
            heading=p.heading,
            text=p.text,
            location=p.location,
            content_hash=content_hash(p.heading, p.text),
        )
        for i, p in enumerate(pieces)
    )
    await tx.flush()
    await indexing.carry_over(tx, version)
    await tx.execute(
        delete(Chunk).where(Chunk.document_id == doc.id, Chunk.version_id != version.id)
    )
    await indexing.enqueue(tx, version)
    return version


async def list_documents(tx: AsyncSession, category_id: uuid.UUID) -> list[Document]:
    await access.require_category(tx, category_id, Level.READ)
    query = (
        select(Document)
        .where(Document.category_id == category_id)
        .order_by(Document.updated_at.desc())
    )
    return list((await tx.scalars(query)).all())


async def get_document(tx: AsyncSession, document_id: uuid.UUID, needed: Level) -> Document:
    doc = await tx.get(Document, document_id)
    if doc is None:
        raise ApiError(404, "document.not_found", "document not found")
    await access.require_category(tx, doc.category_id, needed)
    return doc


async def remove_document(tx: AsyncSession, document_id: uuid.UUID) -> None:
    doc = await get_document(tx, document_id, Level.EDIT)
    await audit.record(
        tx,
        "document.remove",
        project_id=doc.project_id,
        target=audit.Target("document", doc.id),
        details={"title": doc.title},
    )
    await tx.delete(doc)


async def chunk_preview(tx: AsyncSession, document_id: uuid.UUID, limit: int) -> list[Chunk]:
    await get_document(tx, document_id, Level.READ)
    query = select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.ordinal)
    return list((await tx.scalars(query.limit(limit))).all())


async def count_chunks(tx: AsyncSession, document_id: uuid.UUID) -> int:
    return int(await tx.scalar(select(func.count()).where(Chunk.document_id == document_id)) or 0)


async def set_trust(tx: AsyncSession, document_id: uuid.UUID, trust: Trust) -> None:
    doc = await get_document(tx, document_id, Level.EDIT)
    await tx.execute(update(Document).where(Document.id == doc.id).values(trust=trust))
