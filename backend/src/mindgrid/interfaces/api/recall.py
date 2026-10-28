"""/v1/projects/{id}/recall: hybrid search over the project's knowledge. A POST (the query
can be long) that only reads, so an API key with the `read` scope may call it."""

import time
import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from mindgrid.knowledge.evals import log as recall_log
from mindgrid.knowledge.library.models import Trust
from mindgrid.knowledge.recall import service as recall_service
from mindgrid.platform.apikeys.models import KeyScope

from .deps import Tx, key_scope

router = APIRouter(tags=["knowledge"])


class RecallIn(BaseModel):
    query: str = Field(min_length=1, max_length=8000)
    categories: list[uuid.UUID] = Field(default_factory=list[uuid.UUID], max_length=100)
    k: int = Field(0, ge=0, le=200, description="0 = the server default")


class HitOut(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    category_id: uuid.UUID
    title: str
    trust: Trust
    heading: str
    text: str
    location: dict[str, Any]
    score: float
    ranks: dict[str, int]
    distance: float | None = Field(description="Cosine distance, when found by meaning.")
    relevance: float | None = Field(description="Reranker probability 0..1, when reranked.")


class RecallOut(BaseModel):
    hits: list[HitOut]
    skipped: dict[str, str]
    space: str
    reranker: str
    dropped: int = Field(description="Candidates removed as unrelated.")
    rewritten: str = Field("", description="Extra search query from recall.rewrite, if used.")
    recall_id: uuid.UUID | None = Field(None, description="The logged question.")


def _ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


@router.post("/projects/{project_id}/recall", openapi_extra=key_scope(KeyScope.READ))
async def recall(project_id: uuid.UUID, body: RecallIn, tx: Tx) -> RecallOut:
    ask = recall_service.Ask(project_id, body.query, tuple(body.categories), body.k)
    started = time.perf_counter()
    result = await recall_service.recall(tx, ask)
    recall_id = await recall_log.record(tx, "recall", ask, result, _ms(started))
    return RecallOut(
        recall_id=recall_id,
        hits=[HitOut.model_validate(h, from_attributes=True) for h in result.hits],
        skipped=result.skipped,
        space=result.space,
        reranker=result.reranker,
        dropped=result.dropped,
        rewritten=result.rewritten,
    )
