"""/v1/projects/{id}/evals: run a golden set through recall and list past runs, so a
change of model, reranker or cutoff shows up as better or worse numbers."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from mindgrid.knowledge.evals import judge as eval_judge
from mindgrid.knowledge.evals import runner
from mindgrid.knowledge.evals.models import EvalJudgement, EvalRun
from mindgrid.platform.apikeys.models import KeyScope

from .deps import Tx, key_scope

router = APIRouter(tags=["knowledge"])


class JudgementOut(BaseModel):
    id: uuid.UUID
    judge: str
    answerer: str = Field(description="Who wrote the graded answers (empty = none written).")
    metrics: dict[str, float]
    cases: list[dict[str, Any]]
    created_at: datetime

    @classmethod
    def of(cls, j: EvalJudgement) -> JudgementOut:
        return cls(
            id=j.id,
            judge=j.judge,
            answerer=j.answerer,
            metrics=j.metrics,
            cases=j.cases,
            created_at=j.created_at,
        )


class EvalRunOut(BaseModel):
    id: uuid.UUID
    name: str
    k: int
    metrics: dict[str, float]
    setup: dict[str, Any]
    cases: list[dict[str, Any]]
    created_at: datetime
    judging: str | None = Field(None, description="Judge queued for this run (gemini/local).")
    judgements: list[JudgementOut] = Field(default_factory=list[JudgementOut])

    @classmethod
    def of(
        cls, r: EvalRun, judgements: list[EvalJudgement] | None = None, judging: str | None = None
    ) -> EvalRunOut:
        return cls(
            judging=judging,
            judgements=[JudgementOut.of(j) for j in judgements or []],
            id=r.id,
            name=r.name,
            k=r.k,
            metrics=r.metrics,
            setup=r.setup,
            cases=r.cases,
            created_at=r.created_at,
        )


class EvalIn(runner.GoldenSet):
    callback_url: str | None = Field(None, max_length=2000, description="Receives eval.completed.")
    judge: eval_judge.JudgeMode | None = Field(
        None,
        description="Also grade the run with an LLM (a job; eval.judged when done). Use a "
        "stronger model than the one answering.",
    )


@router.post("/projects/{project_id}/evals", status_code=201, openapi_extra=key_scope(KeyScope.RUN))
async def run_eval(project_id: uuid.UUID, body: EvalIn, tx: Tx) -> EvalRunOut:
    golden = runner.GoldenSet(name=body.name, k=body.k, cases=body.cases)
    run = await runner.run(tx, project_id, golden, body.callback_url)
    if body.judge:
        await eval_judge.enqueue(tx, run, body.judge)
    return EvalRunOut.of(run, judging=body.judge)


@router.get("/projects/{project_id}/evals")
async def list_evals(project_id: uuid.UUID, tx: Tx) -> list[EvalRunOut]:
    runs = await runner.list_runs(tx, project_id)
    graded = await eval_judge.for_runs(tx, [r.id for r in runs])
    return [EvalRunOut.of(r, graded.get(r.id, [])) for r in runs]
