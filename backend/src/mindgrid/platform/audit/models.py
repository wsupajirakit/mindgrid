"""Audit events. The app role may insert and read (row-level security), never change or
delete; the actor columns come from the acting principal (database defaults + policy)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mindgrid.db.base import Base, Keyed


class AuditEvent(Keyed, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_project_id_id", "project_id", "id"),
        Index("ix_audit_events_actor_user_id_id", "actor_user_id", "id"),
        # Writers insert without reading back (a system task may not see the event).
        {"implicit_returning": False},
    )

    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Filled in by the database from the acting principal; never passed by the caller.
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), server_default=text("mindgrid_actor()")
    )
    actor_superadmin: Mapped[bool] = mapped_column(
        Boolean, server_default=text("mindgrid_is_superadmin()")
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(64))  # dotted code, e.g. project.create
    target_type: Mapped[str] = mapped_column(String(32), default="")
    target_id: Mapped[str] = mapped_column(String(64), default="")
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    request_id: Mapped[str] = mapped_column(String(64), default="")
