"""Sources (a repository, its mapping, where accepted knowledge goes) and proposals (one
per batch of new commits, items reviewed one by one)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mindgrid.db.base import Base, Keyed, Timestamped


class SynapseSource(Keyed, Timestamped, Base):
    __tablename__ = "synapse_sources"

    name: Mapped[str] = mapped_column(String(100), unique=True)
    path: Mapped[str] = mapped_column(String(1000))  # inside MINDGRID_SYNAPSE_ALLOWED_ROOTS
    mapping: Mapped[dict[str, Any]] = mapped_column(JSONB)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    every_minutes: Mapped[int | None] = mapped_column(Integer)
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_commit: Mapped[str] = mapped_column(String(64), default="")  # "" = never learned
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(server_default=text("mindgrid_actor()"))


class SynapseProposal(Keyed, Base):
    __tablename__ = "synapse_proposals"

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("synapse_sources.id", ondelete="CASCADE")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    from_commit: Mapped[str] = mapped_column(String(64))
    to_commit: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | reviewed
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    redactions: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
