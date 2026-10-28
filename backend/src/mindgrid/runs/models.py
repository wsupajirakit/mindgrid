"""The runs table (project-scoped; viewers read, run-level members start runs)."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mindgrid.db.base import Base, Keyed


class RunStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


def _values(members: type[RunStatus]) -> list[str]:
    return [m.value for m in members]


class Run(Keyed, Base):
    __tablename__ = "runs"
    __table_args__ = (Index("ix_runs_project_id_created_at", "project_id", "created_at"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    playbook_id: Mapped[str] = mapped_column(String(100))
    playbook_version: Mapped[int] = mapped_column(Integer)
    playbook_status: Mapped[str] = mapped_column(String(16))  # status when it ran
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, name="run_status", values_callable=_values), default=RunStatus.QUEUED
    )
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB)
    outputs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    error: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(server_default=text("mindgrid_actor()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
