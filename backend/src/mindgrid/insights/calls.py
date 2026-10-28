"""Results history: every playbook run and every logged question, newest first, with who
asked, when, through which channel, what it used and what came of it. Runs as the caller:
row-level security decides which rows exist (questions: the caller's own, or all of a
project they manage). Names of other people come only through the member-profile function
(members of a project see each other) or, for a superadmin, the users table."""

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.knowledge.evals.models import AnswerRecord, RecallEvent
from mindgrid.knowledge.library.models import Chunk, Document
from mindgrid.platform.identity.directory import Person, people
from mindgrid.platform.tenancy.models import Project
from mindgrid.playbooks import catalog
from mindgrid.runs.models import Run

Kind = Literal["run", "question"]
EXCERPT = 600


@dataclass(slots=True)
class Call:
    kind: Kind
    id: str
    at: str
    project_id: str
    project: str
    actor: Person | None
    title: str
    channel: str
    status: str
    detail: dict[str, Any] = field(default_factory=dict[str, Any])


async def _runs(tx: AsyncSession, project_id: uuid.UUID | None, limit: int) -> list[Any]:
    query = (
        select(Run, Project.name)
        .join(Project, Project.id == Run.project_id)
        .order_by(Run.created_at.desc())
        .limit(limit)
    )
    if project_id:
        query = query.where(Run.project_id == project_id)
    return list((await tx.execute(query)).all())


async def _questions(tx: AsyncSession, project_id: uuid.UUID | None, limit: int) -> list[Any]:
    answered = (
        select(
            AnswerRecord.recall_event_id,
            func.count().label("answers"),
            func.bool_and(AnswerRecord.check_ok).label("ok"),
            func.max(AnswerRecord.writer).label("writer"),
        )
        .group_by(AnswerRecord.recall_event_id)
        .subquery()
    )
    query = (
        select(RecallEvent, Project.name, answered.c.answers, answered.c.ok, answered.c.writer)
        .join(Project, Project.id == RecallEvent.project_id)
        .outerjoin(answered, answered.c.recall_event_id == RecallEvent.id)
        .order_by(RecallEvent.created_at.desc())
        .limit(limit)
    )
    if project_id:
        query = query.where(RecallEvent.project_id == project_id)
    return list((await tx.execute(query)).all())


def _run_call(run: Run, project: str, titles: dict[str, str]) -> Call:
    seconds = (run.finished_at - run.created_at).total_seconds() if run.finished_at else None
    return Call(
        "run",
        str(run.id),
        run.created_at.isoformat(),
        str(run.project_id),
        project,
        None,
        f"{titles.get(run.playbook_id, run.playbook_id)} v{run.playbook_version}",
        "playbook",
        run.status.value,
        {
            "playbook_id": run.playbook_id,
            "seconds": seconds,
            "error": run.error,
            "outputs": sorted(run.outputs),
        },
    )


def _question_call(row: Any) -> Call:
    event, project, answers, ok, writer = row
    status = "no_hits" if not event.chunk_ids else ("answered" if answers else "found")
    return Call(
        "question",
        str(event.id),
        event.created_at.isoformat(),
        str(event.project_id),
        project,
        None,
        event.query,
        event.via,
        status,
        {
            "hits": len(event.chunk_ids),
            "ms": event.elapsed_ms,
            "answers": answers or 0,
            "citations_ok": ok,
            "writer": writer or "",
        },
    )


async def calls(
    tx: AsyncSession, project_id: uuid.UUID | None, kind: Kind | None, limit: int
) -> list[Call]:
    limit = max(1, min(limit, 1000))
    titles = {s["id"]: s["title"] for s in await catalog.summaries(tx, None)}
    out: list[tuple[Call, uuid.UUID | None]] = []
    if kind in (None, "run"):
        out += [
            (_run_call(r, p, titles), r.created_by) for r, p in await _runs(tx, project_id, limit)
        ]
    if kind in (None, "question"):
        out += [
            (_question_call(row), row[0].actor_id)
            for row in await _questions(tx, project_id, limit)
        ]
    named = await people(tx, {uuid.UUID(c.project_id) for c, _ in out})
    for call, actor in out:
        call.actor = named.get(actor) if actor else None
    return sorted((c for c, _ in out), key=lambda c: c.at, reverse=True)[:limit]


async def _passages(tx: AsyncSession, chunk_ids: list[uuid.UUID]) -> list[dict[str, str]]:
    found: dict[uuid.UUID, tuple[Chunk, str]] = {
        chunk.id: (chunk, title)
        for chunk, title in await tx.execute(
            select(Chunk, Document.title)
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.id.in_(chunk_ids))
        )
    }
    out: list[dict[str, str]] = []
    for i, cid in enumerate(chunk_ids, 1):
        chunk, title = found.get(cid, (None, ""))
        out.append(
            {
                "ref": f"P{i}",
                "title": title,
                "heading": chunk.heading if chunk else "",
                "text": chunk.text[:EXCERPT] if chunk else "",  # empty: the chunk is gone
            }
        )
    return out


def _answer(a: AnswerRecord) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "at": a.created_at.isoformat(),
        "channel": a.channel,
        "writer": a.writer,
        "text": a.text,
        "check_ok": a.check_ok,
        "cited": a.cited,
        "unknown": a.unknown,
        "uncited": a.uncited,
    }


async def question(tx: AsyncSession, recall_id: uuid.UUID) -> dict[str, Any]:
    """One logged question: the passages it found and every answer kept for it."""
    row = (
        await tx.execute(
            select(RecallEvent, Project.name)
            .join(Project, Project.id == RecallEvent.project_id)
            .where(RecallEvent.id == recall_id)
        )
    ).first()
    if row is None:
        raise ApiError(404, "insights.not_found", "no such question in what you may see")
    event, project = row
    answers = await tx.scalars(
        select(AnswerRecord)
        .where(AnswerRecord.recall_event_id == recall_id)
        .order_by(AnswerRecord.created_at)
    )
    named = await people(tx, {event.project_id})
    return {
        "id": str(event.id),
        "at": event.created_at.isoformat(),
        "project": project,
        "project_id": str(event.project_id),
        "query": event.query,
        "via": event.via,
        "ms": event.elapsed_ms,
        "skipped": event.skipped,
        "passages": await _passages(tx, event.chunk_ids),
        "actor": named.get(event.actor_id) if event.actor_id else None,
        "answers": [_answer(a) for a in answers],
    }
