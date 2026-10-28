"""The job table. Accounts see the jobs they queued and the jobs of projects they can
view; only the definer functions (claim / finish) change a job after it is queued."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mindgrid.db.base import Base, Keyed, Timestamped
from mindgrid.platform.identity.models import User
from mindgrid.platform.tenancy.models import Project


def _values(members: type[enum.StrEnum]) -> list[str]:
    return [m.value for m in members]


ACTOR_PROJECTS = (
    "coalesce(string_to_array(nullif(current_setting('mindgrid.projects', true), ''), ',')"
    "::uuid[], '{}')"
)


class JobStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Job(Keyed, Timestamped, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_ready", "run_after", postgresql_where=text("status = 'queued'")),
        Index("ix_jobs_project_id", "project_id"),
    )

    kind: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", values_callable=_values), default=JobStatus.QUEUED
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(Project.id, ondelete="CASCADE"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(User.id, ondelete="CASCADE"), server_default=text("mindgrid_actor()")
    )
    # The API-key project limit in force when the job was queued (empty = none).
    actor_projects: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid(as_uuid=True)), server_default=text(ACTOR_PROJECTS)
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker: Mapped[str] = mapped_column(String(64), default="")
    last_error: Mapped[str] = mapped_column(Text, default="")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
