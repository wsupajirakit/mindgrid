"""The knowledge of a project as a network: the project, its categories, their documents
(sized by chunk count), plus links between documents that questions found together (from
the recall log the caller may read). Runs as the caller, so row-level security limits
every part to what they may see."""

import uuid
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.platform.tenancy import access
from mindgrid.platform.tenancy.models import Category, Project

from ..evals.models import RecallEvent
from .models import Chunk, Document

MAX_DOCUMENTS = 300
RECENT_QUESTIONS = 500
MAX_TOGETHER = 80


@dataclass(slots=True)
class Graph:
    nodes: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    edges: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])


async def _together(
    tx: AsyncSession, project_id: uuid.UUID, shown: set[str]
) -> list[dict[str, Any]]:
    events = (
        await tx.scalars(
            select(RecallEvent.chunk_ids)
            .where(RecallEvent.project_id == project_id)
            .order_by(RecallEvent.created_at.desc())
            .limit(RECENT_QUESTIONS)
        )
    ).all()
    chunk_ids = {cid for ids in events for cid in ids}
    owner = {
        cid: str(doc)
        for cid, doc in await tx.execute(
            select(Chunk.id, Chunk.document_id).where(Chunk.id.in_(chunk_ids))
        )
    }
    pairs: Counter[tuple[str, str]] = Counter()
    for ids in events:
        docs = sorted({owner[c] for c in ids if c in owner} & shown)
        pairs.update(combinations(docs, 2))
    return [
        {"source": a, "target": b, "kind": "together", "weight": n}
        for (a, b), n in pairs.most_common(MAX_TOGETHER)
    ]


async def build(tx: AsyncSession, project_id: uuid.UUID) -> Graph:
    await access.require_project_view(tx, project_id)
    project = await tx.get(Project, project_id)
    out = Graph()
    if project is None:
        return out
    out.nodes.append({"id": str(project.id), "kind": "project", "label": project.name})
    for cat in await tx.scalars(select(Category).where(Category.project_id == project_id)):
        out.nodes.append(
            {"id": str(cat.id), "kind": "category", "label": cat.name, "restricted": cat.restricted}
        )
        out.edges.append({"source": str(project.id), "target": str(cat.id), "kind": "contains"})
    chunks = (
        select(Chunk.document_id, func.count().label("n"))
        .where(Chunk.project_id == project_id)
        .group_by(Chunk.document_id)
        .subquery()
    )
    documents = await tx.execute(
        select(Document, func.coalesce(chunks.c.n, 0))
        .outerjoin(chunks, chunks.c.document_id == Document.id)
        .where(Document.project_id == project_id)
        .order_by(Document.updated_at.desc())
        .limit(MAX_DOCUMENTS)
    )
    shown: set[str] = set()
    for doc, n in documents:
        shown.add(str(doc.id))
        out.nodes.append(
            {
                "id": str(doc.id),
                "kind": "document",
                "label": doc.title,
                "chunks": n,
                "trust": doc.trust.value,
                "category_id": str(doc.category_id),
            }
        )
        out.edges.append(
            {"source": str(doc.category_id), "target": str(doc.id), "kind": "contains"}
        )
    out.edges += await _together(tx, project_id, shown)
    return out
