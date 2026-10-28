"""Events the job queue sends: `job.failed` when a job gives up (any kind), so a caller
waiting on a callback learns about failures the job itself could not report."""

import uuid

from mindgrid.db.session import transaction
from mindgrid.platform.events import service as events
from mindgrid.platform.events import types

from .queue import Claimed


class JobFailed(types.EventData):
    job_id: str
    kind: str
    attempts: int
    error: str
    links: types.Links


JOB_FAILED = types.define(
    "job.failed", "A background job failed for good (after its retries).", JobFailed
)


async def failed(job: Claimed, error: str) -> None:
    if job.actor.user_id is None:
        return
    project = job.payload.get("_project")
    project_id = uuid.UUID(project) if project else None
    ui = f"/projects/{project_id}" if project_id else "/"
    data = JobFailed(
        job_id=str(job.id),
        kind=job.kind,
        attempts=job.attempts,
        error=error[:500],
        links=events.link(f"/v1/jobs/{job.id}", ui),
    )
    async with transaction(job.actor) as tx:
        await events.emit(
            tx,
            data,
            project_id=project_id,
            subject=str(job.payload.get("subject") or f"jobs/{job.id}"),
        )
