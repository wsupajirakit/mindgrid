"""Documents, their versions (with the original file) and chunks. Every row carries its
project and category, so row-level security and search filters work in one query."""

import enum
import hashlib
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from mindgrid.db.base import Base, Keyed, Timestamped


def _values(members: type[enum.StrEnum]) -> list[str]:
    return [m.value for m in members]


class Trust(enum.StrEnum):
    """How far a document's claims are established (shown with every citation)."""

    UNRATED = "unrated"
    VERIFIED = "verified"
    CLAIMED = "claimed"
    DISPUTED = "disputed"


class VersionStatus(enum.StrEnum):
    PENDING = "pending"
    PARSED = "parsed"
    INDEXED = "indexed"
    FAILED = "failed"


class Document(Keyed, Timestamped, Base):
    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_category_id", "category_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(300))
    trust: Mapped[Trust] = mapped_column(
        Enum(Trust, name="document_trust", values_callable=_values), default=Trust.UNRATED
    )
    source: Mapped[str] = mapped_column(String(32), default="upload")  # upload|bridge|synapse
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(server_default=text("mindgrid_actor()"))


class DocumentVersion(Keyed, Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_document_versions_document_version"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    blob: Mapped[bytes] = mapped_column(LargeBinary)
    status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus, name="version_status", values_callable=_values),
        default=VersionStatus.PENDING,
    )
    error: Mapped[str] = mapped_column(Text, default="")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Chunk(Keyed, Base):
    __tablename__ = "chunks"
    __table_args__ = (
        Index("ix_chunks_category_id", "category_id"),
        Index("ix_chunks_version_id_ordinal", "version_id", "ordinal"),
        Index("ix_chunks_project_id_content_hash", "project_id", "content_hash"),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_chunks_text_trgm",
            "text",
            postgresql_using="gin",
            postgresql_ops={"text": "gin_trgm_ops"},
        ),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    ordinal: Mapped[int] = mapped_column(Integer)
    heading: Mapped[str] = mapped_column(Text, default="")
    text: Mapped[str] = mapped_column(Text)
    location: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # page, rows, ...
    # SHA-256 of embed_text(): an unchanged chunk in a new version reuses its vector.
    content_hash: Mapped[bytes] = mapped_column(LargeBinary)
    # Optional LLM-written line placing the chunk in its document (index.contextualize).
    context: Mapped[str] = mapped_column(Text, default="", server_default="")
    # 'simple' config: no stemming or stop words, so every language is indexed the same way;
    # trigram search (ix_chunks_text_trgm) covers scripts without spaces such as Thai.
    tsv: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple', context || ' ' || heading || ' ' || text)", persisted=True),
    )


def embed_text(heading: str, text: str) -> str:
    """The exact text an embedder receives for a chunk (the migration backfill mirrors it)."""
    return f"{heading}\n{text}" if heading else text


def content_hash(heading: str, text: str) -> bytes:
    return hashlib.sha256(embed_text(heading, text).encode()).digest()
