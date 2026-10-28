"""Run a golden set through recall (the same path as real questions, minus logging) and
store the scores with the setup that produced them."""

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.platform.events import service as events
from mindgrid.platform.tenancy import access

from ..recall import config as recall_config
from ..recall import service as recall_service
from . import config as eval_config
from . import events as eval_events
from . import metrics
from .models import EvalRun


class Case(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    expect: list[str] = Field(
        default_factory=list[str],
        max_length=50,
        description='Title or "title#heading" fragments; empty = off-topic (expect nothing).',
    )
    categories: list[uuid.UUID] = Field(default_factory=list[uuid.UUID], max_length=100)


class GoldenSet(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    k: int = Field(5, ge=1, le=50)
    cases: list[Case] = Field(min_length=1)


@dataclass(slots=True)
class _Setup:
    space: str = ""
    reranker: str = ""
    skipped: dict[str, str] = field(default_factory=dict[str, str])


def _setup_of(found: recall_service.Recall, setup: _Setup) -> None:
    setup.space = setup.space or found.space
    setup.reranker = setup.reranker or found.reranker
    setup.skipped |= found.skipped


async def _cases(
    tx: AsyncSession, project_id: uuid.UUID, golden: GoldenSet, setup: _Setup
) -> tuple[list[metrics.CaseScore], list[dict[str, Any]]]:
    scores: list[metrics.CaseScore] = []
    rows: list[dict[str, Any]] = []
    for case in golden.cases:
        ask = recall_service.Ask(project_id, case.query, tuple(case.categories), golden.k)
        found = await recall_service.recall(tx, ask)
        _setup_of(found, setup)
        got = [(h.title, h.heading) for h in found.hits]
        result = metrics.score(case.expect, got, golden.k)
        scores.append(result)
        found_refs = [f"{t}#{h}" for t, h in got]
        rows.append(
            {"query": case.query, "expect": case.expect, **asdict(result), "found": found_refs}
        )
    return scores, rows


async def run(
    tx: AsyncSession, project_id: uuid.UUID, golden: GoldenSet, callback_url: str | None = None
) -> EvalRun:
    await access.require_project_view(tx, project_id)
    limit = eval_config.get_settings().max_cases
    if len(golden.cases) > limit:
        raise ApiError(400, "eval.too_many_cases", "too many cases", params={"max": limit})
    setup = _Setup()
    scores, rows = await _cases(tx, project_id, golden, setup)
    cfg = recall_config.get_settings()
    snapshot: dict[str, Any] = {
        **asdict(setup),
        "min_relevance": cfg.min_relevance,
        "max_vector_distance": cfg.max_vector_distance,
    }
    record = EvalRun(
        project_id=project_id,
        name=golden.name,
        k=golden.k,
        metrics=metrics.summary(scores),
        setup=snapshot,
        cases=rows,
    )
    tx.add(record)
    await tx.flush()
    await tx.refresh(record)
    data = eval_events.EvalCompleted(
        eval_run_id=str(record.id),
        name=record.name,
        k=record.k,
        metrics=record.metrics,
        links=events.link(f"/v1/projects/{project_id}/evals", f"/projects/{project_id}?tab=ask"),
    )
    if callback_url:
        await events.register_callback(
            tx, f"evals/{record.id}", project_id, callback_url, [eval_events.EVAL_COMPLETED.name]
        )
    await events.emit(tx, data, project_id=project_id, subject=f"evals/{record.id}")
    return record


async def list_runs(tx: AsyncSession, project_id: uuid.UUID, limit: int = 50) -> list[EvalRun]:
    await access.require_project_view(tx, project_id)
    query = (
        select(EvalRun)
        .where(EvalRun.project_id == project_id)
        .order_by(EvalRun.created_at.desc())
        .limit(limit)
    )
    return list((await tx.scalars(query)).all())
