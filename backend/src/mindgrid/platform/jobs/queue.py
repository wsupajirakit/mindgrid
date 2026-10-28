"""Queue, claim and finish jobs. `enqueue` runs inside the caller's transaction, so a job
exists exactly when the change that needs it is committed. Claim and finish go through
SECURITY DEFINER functions: a worker sees no job row of its own accord."""

import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.db.session import Actor

from . import config as job_config
from .models import Job


@dataclass(frozen=True, slots=True)
class Claimed:
    id: uuid.UUID
    kind: str
    payload: dict[str, Any]
    attempts: int
    actor: Actor


@dataclass(frozen=True, slots=True)
class NewJob:
    kind: str
    payload: dict[str, Any] = field(default_factory=dict[str, Any])
    project_id: uuid.UUID | None = None


async def enqueue(tx: AsyncSession, job: NewJob) -> Job:
    """The queuing account and its API-key project limit are filled in by the database."""
    payload = {**job.payload, "_project": str(job.project_id) if job.project_id else None}
    row = Job(
        kind=job.kind,
        payload=payload,
        project_id=job.project_id,
        max_attempts=job_config.get_settings().max_attempts,
    )
    tx.add(row)
    await tx.flush()
    return row


async def claim(tx: AsyncSession, worker: str, kinds: list[str]) -> Claimed | None:
    lease = timedelta(seconds=job_config.get_settings().lease_seconds)
    found = (
        (
            await tx.execute(
                text("select * from mindgrid_claim_job(:worker, :lease, :kinds)"),
                {"worker": worker, "lease": lease, "kinds": kinds},
            )
        )
        .mappings()
        .first()
    )
    if found is None:
        return None
    actor = Actor(
        user_id=found["created_by"],
        superadmin=bool(found["actor_superadmin"]),
        projects=tuple(found["actor_projects"] or ()),
    )
    return Claimed(found["id"], found["kind"], dict(found["payload"]), found["attempts"], actor)


def retry_delay(attempts: int) -> timedelta:
    base = job_config.get_settings().retry_base_seconds
    return timedelta(seconds=base * 2 ** max(attempts - 1, 0))


@dataclass(frozen=True, slots=True)
class Outcome:
    error: str | None = None  # None = done
    final: bool = False  # retrying cannot help


async def finish(tx: AsyncSession, job: Claimed, worker: str, outcome: Outcome) -> str | None:
    """Mark done, or record the error and queue the next try (failed when final or after
    the last try). Returns the new status, or None when the lease was lost to another worker."""
    status = await tx.scalar(
        text("select mindgrid_finish_job(:id, :worker, :error, :final, :retry)"),
        {
            "id": job.id,
            "worker": worker,
            "error": outcome.error,
            "final": outcome.final,
            "retry": retry_delay(job.attempts),
        },
    )
    return None if status is None else str(status)


async def extend(tx: AsyncSession, job: Claimed, worker: str) -> bool:
    """Push the lease forward while the job still runs; False when it was lost."""
    lease = timedelta(seconds=job_config.get_settings().lease_seconds)
    found = await tx.scalar(
        text("select mindgrid_extend_job_lease(:id, :worker, :lease)"),
        {"id": job.id, "worker": worker, "lease": lease},
    )
    return bool(found)
