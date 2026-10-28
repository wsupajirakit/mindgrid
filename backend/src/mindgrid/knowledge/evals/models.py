"""Eval runs (golden set results, kept to compare runs), the recall log (real questions,
kept for a limited time to build golden sets from) and the answers written to them (by the
server, or reported back by a client such as an MCP host). An answer goes with its question
when the log is purged."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
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

from mindgrid.db.base import Base, Keyed


class EvalRun(Keyed, Base):
    __tablename__ = "eval_runs"
    __table_args__ = (Index("ix_eval_runs_project_id_created_at", "project_id", "created_at"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    k: Mapped[int] = mapped_column(Integer)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB)
    setup: Mapped[dict[str, Any]] = mapped_column(JSONB)  # space, reranker, cutoffs
    cases: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)  # per-case scores and results
    created_by: Mapped[uuid.UUID | None] = mapped_column(server_default=text("mindgrid_actor()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RecallEvent(Keyed, Base):
    __tablename__ = "recall_events"
    __table_args__ = (Index("ix_recall_events_project_id_created_at", "project_id", "created_at"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(server_default=text("mindgrid_actor()"))
    via: Mapped[str] = mapped_column(String(32))  # recall | context-pack | answer
    query: Mapped[str] = mapped_column(Text)
    chunk_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid(as_uuid=True)))
    skipped: Mapped[dict[str, str]] = mapped_column(JSONB)
    elapsed_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvalJudgement(Keyed, Base):
    """An LLM's grading of one eval run (append-only, like the run itself)."""

    __tablename__ = "eval_judgements"
    __table_args__ = (Index("ix_eval_judgements_eval_run_id", "eval_run_id"),)

    eval_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("eval_runs.id", ondelete="CASCADE"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    judge: Mapped[str] = mapped_column(String(200))  # provider:model that graded
    answerer: Mapped[str] = mapped_column(String(200))  # provider:model that answered, or ""
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB)
    cases: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    created_by: Mapped[uuid.UUID | None] = mapped_column(server_default=text("mindgrid_actor()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnswerRecord(Keyed, Base):
    __tablename__ = "answers"
    __table_args__ = (Index("ix_answers_recall_event_id", "recall_event_id"),)

    recall_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recall_events.id", ondelete="CASCADE")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(server_default=text("mindgrid_actor()"))
    channel: Mapped[str] = mapped_column(String(16))  # web | api | mcp | cli
    writer: Mapped[str] = mapped_column(String(200))  # provider:model or mcp:<client>
    text: Mapped[str] = mapped_column(Text)
    check_ok: Mapped[bool | None] = mapped_column(Boolean)
    cited: Mapped[list[str]] = mapped_column(ARRAY(String(16)), default=list)
    unknown: Mapped[list[str]] = mapped_column(ARRAY(String(16)), default=list)
    uncited: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
