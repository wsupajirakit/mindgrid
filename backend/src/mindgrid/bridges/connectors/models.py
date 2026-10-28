"""Connectors per project, with their schedule and the outcome of the last sync."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mindgrid.db.base import Base, Keyed, Timestamped


class Connector(Keyed, Timestamped, Base):
    __tablename__ = "connectors"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_connectors_project_name"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    every_minutes: Mapped[int | None] = mapped_column(Integer)  # None = only on request
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str] = mapped_column(String(16), default="never")  # ok | failed
    last_error: Mapped[str] = mapped_column(Text, default="")
    last_changed: Mapped[list[str]] = mapped_column(JSONB, default=list)  # datasets updated
    created_by: Mapped[uuid.UUID | None] = mapped_column(server_default=text("mindgrid_actor()"))
