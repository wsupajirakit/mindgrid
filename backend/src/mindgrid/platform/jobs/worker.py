"""The worker loop: claim one job, run its handler in the queuing account's name, record
the outcome. A crash mid-job only loses the lease; the job is claimed again later."""

import asyncio
import contextlib
import os
import time
import uuid

import structlog

from mindgrid.db.session import SYSTEM, transaction

from . import config as job_config
from . import events as job_events
from . import handlers, queue

log = structlog.get_logger(__name__)


def worker_name() -> str:
    """Random per process: worker names land in rows and logs, so no machine name is used."""
    return f"worker-{uuid.uuid4().hex[:8]}-{os.getpid()}"


async def _run(job: queue.Claimed) -> queue.Outcome:
    handler = handlers.get(job.kind)
    if handler is None:
        return queue.Outcome(f"no handler for job kind {job.kind!r}", final=True)
    if job.actor.user_id is None:
        return queue.Outcome("the account that queued this job is gone or disabled", final=True)
    try:
        await handler(job.actor, job.payload)
    except handlers.PermanentJobError as err:
        return queue.Outcome(str(err), final=True)
    except Exception as err:  # any failure is recorded on the job and retried
        log.warning("job.failed", job_id=str(job.id), kind=job.kind, error=repr(err))
        return queue.Outcome(repr(err)[:2000])
    return queue.Outcome()


async def _heartbeat(job: queue.Claimed, worker: str) -> None:
    """Keep the lease while the handler runs (a long job is not handed to another worker)."""
    every = job_config.get_settings().lease_seconds / 3
    while True:
        await asyncio.sleep(every)
        async with transaction(SYSTEM) as tx:
            if not await queue.extend(tx, job, worker):
                log.warning("job.lease_lost", job_id=str(job.id), kind=job.kind)
                return


async def _run_with_lease(job: queue.Claimed, worker: str) -> queue.Outcome:
    beat = asyncio.create_task(_heartbeat(job, worker))
    try:
        return await _run(job)
    finally:
        beat.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await beat


async def run_once(worker: str) -> bool:
    """Process one job if one is ready. Returns False when the queue was empty."""
    async with transaction(SYSTEM) as tx:
        job = await queue.claim(tx, worker, handlers.kinds())
    if job is None:
        return False
    outcome = await _run_with_lease(job, worker)
    async with transaction(SYSTEM) as tx:
        status = await queue.finish(tx, job, worker, outcome)
    log.info("job.finished", job_id=str(job.id), kind=job.kind, status=status)
    if status == "failed":
        try:
            await job_events.failed(job, outcome.error or "")
        except Exception as err:  # reporting must never stop the job loop
            log.warning("job.failed_event", job_id=str(job.id), error=repr(err))
    return True


async def run_until_empty(worker: str, limit: int = 1000) -> int:
    done = 0
    while done < limit and await run_once(worker):
        done += 1
    return done


async def run_due(last: dict[str, float]) -> None:
    """Run the periodic tasks whose interval has passed (a failure is logged, not fatal)."""
    now = time.monotonic()
    for name, (seconds, task) in handlers.periodic().items():
        if now - last.get(name, float("-inf")) < seconds:
            continue
        last[name] = now
        try:
            await task()
        except Exception as err:  # maintenance must never stop the job loop
            log.warning("periodic.failed", task=name, error=repr(err))


async def run_forever(worker: str, stop: asyncio.Event) -> None:
    idle = job_config.get_settings().idle_seconds
    last: dict[str, float] = {}
    while not stop.is_set():
        await run_due(last)
        if not await run_once(worker):
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=idle)
