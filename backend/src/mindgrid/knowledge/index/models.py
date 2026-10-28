"""Embedding spaces and chunk vectors. One column holds vectors of any size; each space
gets its own partial HNSW index (cast to its size), created with the space, so vectors from
different models are never compared and adding a model needs no migration."""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from mindgrid.db.base import Base

from ..library.models import Chunk


class EmbeddingSpace(Base):
    __tablename__ = "embedding_spaces"

    key: Mapped[str] = mapped_column(String(300), primary_key=True)  # provider:model@dims
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(200))
    dims: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"
    __table_args__ = (Index("ix_chunk_embeddings_category_id", "category_id"),)

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(Chunk.id, ondelete="CASCADE"), primary_key=True
    )
    space: Mapped[str] = mapped_column(
        ForeignKey("embedding_spaces.key", ondelete="CASCADE"), primary_key=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    embedding: Mapped[list[float]] = mapped_column(Vector())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
