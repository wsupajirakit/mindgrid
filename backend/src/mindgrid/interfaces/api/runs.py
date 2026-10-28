"""/v1/projects/{id}/runs and /v1/runs/{id}: start a playbook run (queued for the worker)
and read runs. `wait_seconds` holds the response until the run ends (or the wait does)."""

import asyncio
import time
import uuid
from datetime import datetime
from typing import Any, cast

from fastapi import APIRouter
from pydantic import BaseModel, Field

from mindgrid.db.session import transaction
from mindgrid.platform.apikeys.models import KeyScope
from mindgrid.runs import service as runs
from mindgrid.runs.models import Run, RunStatus

from .deps import CurrentPrincipal, Tx, key_scope

router = APIRouter(tags=["playbooks"])
CALLBACK_DOC = (
    "Receives run.completed, run.failed or job.failed for this run (signed, see /v1/events)."
)
POLL_SECONDS = 0.25


class RunIn(BaseModel):
    playbook: str
    version: int | None = Field(None, ge=1)
    params: dict[str, Any] = Field(default_factory=dict[str, Any])
    inputs: dict[str, Any] = Field(default_factory=dict[str, Any])
    wait_seconds: float = Field(0, ge=0, le=60)
    callback_url: str | None = Field(None, max_length=2000, description=CALLBACK_DOC)


class RunOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    playbook_id: str
    playbook_version: int
    playbook_status: str
    status: RunStatus
    params: dict[str, Any]
    inputs: dict[str, Any] = Field(
        default_factory=dict[str, Any],
        description="What each input was: the pinned dataset (name, version) or, for data "
        "sent inline, its size (rows) — never the data itself.",
    )
    outputs: dict[str, Any]
    steps: list[dict[str, Any]]
    error: str
    created_at: datetime
    finished_at: datetime | None

    @classmethod
    def of(cls, r: Run) -> RunOut:
        out = cls.model_validate(r, from_attributes=True)
        out.inputs = {name: _input_summary(value) for name, value in r.inputs.items()}
        return out


def _input_summary(value: object) -> dict[str, object]:
    if isinstance(value, list):
        return {"rows": len(cast(list[object], value))}
    if isinstance(value, dict):
        pinned = cast(dict[str, object], value)
        if "dataset" in pinned:
            return {k: pinned[k] for k in ("dataset", "version") if k in pinned}
    kind: str = type(cast(object, value)).__name__
    return {"type": kind}


@router.post("/projects/{project_id}/runs", status_code=201, openapi_extra=key_scope(KeyScope.RUN))
async def start_run(project_id: uuid.UUID, body: RunIn, principal: CurrentPrincipal) -> RunOut:
    ask = runs.Start(
        project_id, body.playbook, body.version, body.params, body.inputs, body.callback_url
    )
    async with transaction(principal.actor) as tx:
        run = await runs.start(tx, ask)
    deadline = time.monotonic() + body.wait_seconds
    while run.status in {RunStatus.QUEUED, RunStatus.RUNNING} and time.monotonic() < deadline:
        await asyncio.sleep(POLL_SECONDS)
        async with transaction(principal.actor) as tx:
            run = await runs.get(tx, run.id)
    return RunOut.of(run)


@router.get("/projects/{project_id}/runs")
async def list_runs(project_id: uuid.UUID, tx: Tx) -> list[RunOut]:
    return [RunOut.of(r) for r in await runs.page(tx, project_id)]


@router.get("/runs/{run_id}")
async def get_run(run_id: uuid.UUID, tx: Tx) -> RunOut:
    return RunOut.of(await runs.get(tx, run_id))
