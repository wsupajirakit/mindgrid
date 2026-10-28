"""/v1/insights: the dashboard summary (calls per project, category and playbook over a
window of days) and the results history (who called what, when, with what result). Both
show only what the caller may see."""

import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from mindgrid.insights import calls as calls_service
from mindgrid.insights import summary as summary_service
from mindgrid.platform.apikeys.models import KeyScope

from .deps import Tx, key_scope

router = APIRouter(prefix="/insights", tags=["insights"])


class SummaryOut(BaseModel):
    days: int
    since: datetime
    totals: dict[str, int]
    runs_by_playbook: list[dict[str, Any]]
    runs_by_project: list[dict[str, Any]]
    runs_daily: list[dict[str, Any]]
    questions_daily: list[dict[str, Any]]
    questions_by_project: list[dict[str, Any]]
    hits_by_category: list[dict[str, Any]]
    documents_by_category: list[dict[str, Any]]
    answers_by_channel: list[dict[str, Any]]
    events_by_type: list[dict[str, Any]]


class PersonOut(BaseModel):
    name: str
    email: str
    avatar: str


class CallOut(BaseModel):
    kind: Literal["run", "question"]
    id: str
    at: str
    project_id: str
    project: str
    actor: PersonOut | None
    title: str
    channel: str
    status: str
    detail: dict[str, Any]


class AnswerOut(BaseModel):
    id: str
    at: str
    channel: str
    writer: str
    text: str
    check_ok: bool | None
    cited: list[str]
    unknown: list[str]
    uncited: int


class PassageOut(BaseModel):
    ref: str
    title: str
    heading: str
    text: str


class QuestionOut(BaseModel):
    id: str
    at: str
    project: str
    project_id: str
    query: str
    via: str
    ms: int
    skipped: dict[str, str]
    passages: list[PassageOut]
    actor: PersonOut | None
    answers: list[AnswerOut]


@router.get("/summary", openapi_extra=key_scope(KeyScope.READ))
async def summary(
    tx: Tx,
    days: int = Query(30, ge=1, le=summary_service.MAX_DAYS),
    project_id: uuid.UUID | None = None,
) -> SummaryOut:
    return SummaryOut(**asdict(await summary_service.summary(tx, days, project_id)))


@router.get("/calls", openapi_extra=key_scope(KeyScope.READ))
async def list_calls(
    tx: Tx,
    project_id: uuid.UUID | None = None,
    kind: Literal["run", "question"] | None = None,
    limit: int = Query(300, ge=1, le=1000),
) -> list[CallOut]:
    found = await calls_service.calls(tx, project_id, kind, limit)
    return [CallOut.model_validate(asdict(c)) for c in found]


@router.get("/questions/{recall_id}", openapi_extra=key_scope(KeyScope.READ))
async def question(recall_id: uuid.UUID, tx: Tx) -> QuestionOut:
    found = await calls_service.question(tx, recall_id)
    actor = found.pop("actor")
    return QuestionOut(**found, actor=PersonOut(**asdict(actor)) if actor else None)
