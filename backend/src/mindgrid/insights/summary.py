"""Usage summary for the dashboard: what was called, how often, per project, category and
playbook, over a window of days. Every query runs as the caller, so row-level security
limits it to what the caller may see (questions: their own, or every one in projects they
manage)."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import String, cast, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.datasets.models import Dataset
from mindgrid.knowledge.evals.models import AnswerRecord, RecallEvent
from mindgrid.knowledge.library.models import Chunk, Document
from mindgrid.platform.events.models import Event
from mindgrid.platform.tenancy.models import Category, Project
from mindgrid.playbooks import catalog
from mindgrid.runs.models import Run

MAX_DAYS = 365


@dataclass(slots=True)
class Summary:
    days: int
    since: datetime
    totals: dict[str, int] = field(default_factory=dict[str, int])
    runs_by_playbook: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    runs_by_project: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    runs_daily: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    questions_daily: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    questions_by_project: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    hits_by_category: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    documents_by_category: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    answers_by_channel: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    events_by_type: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])


def _scoped(query: Any, column: Any, project_id: uuid.UUID | None) -> Any:
    """`query` limited to one project when one is given."""
    return query.where(column == project_id) if project_id else query


async def _rows(tx: AsyncSession, query: Any) -> list[tuple[Any, ...]]:
    return [tuple(r) for r in (await tx.execute(query)).all()]


def _day(column: Any) -> Any:
    """The calendar day as text. Constants are literal SQL, not bound values, so the select
    list and GROUP BY render the very same expression."""
    return func.to_char(
        func.date_trunc(literal_column("'day'"), column), literal_column("'YYYY-MM-DD'")
    )


async def _totals(tx: AsyncSession, since: datetime, pid: uuid.UUID | None) -> dict[str, int]:
    async def count(query: Any, column: Any) -> int:
        return int(await tx.scalar(_scoped(query, column, pid)) or 0)

    n = func.count()
    return {
        "projects": await count(select(n).select_from(Project), Project.id),
        "categories": await count(select(n).select_from(Category), Category.project_id),
        "documents": await count(select(n).select_from(Document), Document.project_id),
        "chunks": await count(select(n).select_from(Chunk), Chunk.project_id),
        "datasets": await count(select(n).select_from(Dataset), Dataset.project_id),
        "runs": await count(select(n).where(Run.created_at >= since), Run.project_id),
        "questions": await count(
            select(n).where(RecallEvent.created_at >= since), RecallEvent.project_id
        ),
        "answers": await count(
            select(n).where(AnswerRecord.created_at >= since), AnswerRecord.project_id
        ),
        "events": await count(select(n).where(Event.created_at >= since), Event.project_id),
    }


async def _runs(tx: AsyncSession, out: Summary, pid: uuid.UUID | None) -> None:
    status = cast(Run.status, String)
    rows = await _rows(
        tx,
        _scoped(
            select(Run.playbook_id, status, func.count())
            .where(Run.created_at >= out.since)
            .group_by(Run.playbook_id, status),
            Run.project_id,
            pid,
        ),
    )
    titles = {s["id"]: s["title"] for s in await catalog.summaries(tx, None)}
    per: dict[str, dict[str, Any]] = {}
    for playbook_id, state, total in rows:
        entry = per.setdefault(
            playbook_id,
            {
                "playbook_id": playbook_id,
                "title": titles.get(playbook_id, playbook_id),
                "done": 0,
                "failed": 0,
                "other": 0,
                "total": 0,
            },
        )
        key = state if state in ("done", "failed") else "other"
        entry[key] += total
        entry["total"] += total
    out.runs_by_playbook = sorted(per.values(), key=lambda e: -e["total"])
    daily = await _rows(
        tx,
        _scoped(
            select(_day(Run.created_at), status, func.count())
            .where(Run.created_at >= out.since)
            .group_by(_day(Run.created_at), status),
            Run.project_id,
            pid,
        ),
    )
    days: dict[str, dict[str, Any]] = {}
    for day, state, total in daily:
        entry = days.setdefault(day, {"day": day, "done": 0, "failed": 0, "other": 0})
        entry[state if state in ("done", "failed") else "other"] += total
    out.runs_daily = sorted(days.values(), key=lambda e: e["day"])


async def _per_project(
    tx: AsyncSession, model: Any, since: datetime, pid: uuid.UUID | None
) -> list[dict[str, Any]]:
    rows = await _rows(
        tx,
        _scoped(
            select(Project.id, Project.name, func.count(model.id))
            .join(model, model.project_id == Project.id)
            .where(model.created_at >= since)
            .group_by(Project.id, Project.name),
            Project.id,
            pid,
        ),
    )
    found = [{"project_id": str(i), "name": name, "total": total} for i, name, total in rows]
    return sorted(found, key=lambda e: -e["total"])


async def _questions(tx: AsyncSession, out: Summary, pid: uuid.UUID | None) -> None:
    rows = await _rows(
        tx,
        _scoped(
            select(_day(RecallEvent.created_at), RecallEvent.via, func.count())
            .where(RecallEvent.created_at >= out.since)
            .group_by(_day(RecallEvent.created_at), RecallEvent.via),
            RecallEvent.project_id,
            pid,
        ),
    )
    days: dict[str, dict[str, Any]] = {}
    for day, via, total in rows:
        entry = days.setdefault(day, {"day": day, "recall": 0, "context-pack": 0, "answer": 0})
        entry[via] = entry.get(via, 0) + total
    out.questions_daily = sorted(days.values(), key=lambda e: e["day"])
    channels = await _rows(
        tx,
        _scoped(
            select(
                AnswerRecord.channel,
                func.count(),
                func.count().filter(AnswerRecord.check_ok.is_(True)),
            )
            .where(AnswerRecord.created_at >= out.since)
            .group_by(AnswerRecord.channel),
            AnswerRecord.project_id,
            pid,
        ),
    )
    out.answers_by_channel = [{"channel": c, "total": total, "ok": ok} for c, total, ok in channels]


async def _categories(tx: AsyncSession, out: Summary, pid: uuid.UUID | None) -> None:
    hit = func.unnest(RecallEvent.chunk_ids).table_valued("chunk_id").render_derived()
    hits = (
        select(Chunk.category_id, func.count().label("hits"))
        .select_from(RecallEvent)
        .join(hit, literal_column("true"))
        .join(Chunk, Chunk.id == hit.c.chunk_id)
        .where(RecallEvent.created_at >= out.since)
        .group_by(Chunk.category_id)
        .subquery()
    )
    docs = (
        select(Document.category_id, func.count().label("documents"))
        .group_by(Document.category_id)
        .subquery()
    )
    chunks = (
        select(Chunk.category_id, func.count().label("chunks"))
        .group_by(Chunk.category_id)
        .subquery()
    )
    rows = await _rows(
        tx,
        _scoped(
            select(
                Category.id,
                Category.name,
                Project.name,
                func.coalesce(hits.c.hits, 0),
                func.coalesce(docs.c.documents, 0),
                func.coalesce(chunks.c.chunks, 0),
            )
            .join(Project, Project.id == Category.project_id)
            .outerjoin(hits, hits.c.category_id == Category.id)
            .outerjoin(docs, docs.c.category_id == Category.id)
            .outerjoin(chunks, chunks.c.category_id == Category.id),
            Category.project_id,
            pid,
        ),
    )
    items = [
        {
            "category_id": str(i),
            "name": name,
            "project": project,
            "hits": h,
            "documents": d,
            "chunks": c,
        }
        for i, name, project, h, d, c in rows
    ]
    out.hits_by_category = sorted((x for x in items if x["hits"]), key=lambda e: -e["hits"])
    out.documents_by_category = sorted(items, key=lambda e: -e["documents"])


async def summary(tx: AsyncSession, days: int, project_id: uuid.UUID | None) -> Summary:
    days = max(1, min(days, MAX_DAYS))
    out = Summary(days=days, since=datetime.now(UTC) - timedelta(days=days))
    out.totals = await _totals(tx, out.since, project_id)
    await _runs(tx, out, project_id)
    out.runs_by_project = await _per_project(tx, Run, out.since, project_id)
    out.questions_by_project = await _per_project(tx, RecallEvent, out.since, project_id)
    await _questions(tx, out, project_id)
    await _categories(tx, out, project_id)
    rows = await _rows(
        tx,
        _scoped(
            select(Event.type, func.count())
            .where(Event.created_at >= out.since)
            .group_by(Event.type),
            Event.project_id,
            project_id,
        ),
    )
    out.events_by_type = sorted(
        ({"type": t, "total": n} for t, n in rows), key=lambda e: -e["total"]
    )
    return out
