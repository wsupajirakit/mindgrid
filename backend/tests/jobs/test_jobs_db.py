"""The job queue: same-transaction enqueue, retries with backoff, final failure, the
queuing account's rights, and job visibility."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from sqlalchemy import select, update

from mindgrid.db.session import Actor, transaction
from mindgrid.platform.identity import users
from mindgrid.platform.identity.models import User, UserStatus
from mindgrid.platform.jobs import handlers, queue, worker
from mindgrid.platform.jobs.models import Job, JobStatus

pytestmark = [pytest.mark.anyio, pytest.mark.db]
ROOT = Actor(None, superadmin=True)
OwnerSql = Callable[[str], Awaitable[None]]
SEEN: list[tuple[uuid.UUID | None, dict[str, Any]]] = []


async def _ok(actor: Actor, payload: dict[str, Any]) -> None:
    SEEN.append((actor.user_id, payload))


async def _boom(_actor: Actor, _payload: dict[str, Any]) -> None:
    raise RuntimeError("model offline")


async def _bad(_actor: Actor, _payload: dict[str, Any]) -> None:
    raise handlers.PermanentJobError("payload needs a version_id")


for _kind, _fn in (("test.ok", _ok), ("test.boom", _boom), ("test.bad", _bad)):
    handlers.register(_kind, _fn)


async def _user(name: str) -> uuid.UUID:
    async with transaction(ROOT) as tx:
        user = await users.create_user(
            tx, email=f"{name}@example.com", display_name=name, password="Test-pass-1"
        )
        return user.id


async def _queue(actor: Actor, kind: str) -> uuid.UUID:
    async with transaction(actor) as tx:
        return (await queue.enqueue(tx, queue.NewJob(kind, {"n": 1}))).id


async def _job(job_id: uuid.UUID) -> Job:
    async with transaction(ROOT) as tx:
        job = await tx.get(Job, job_id)
        assert job is not None
        return job


async def test_job_runs_as_the_account_that_queued_it(db: None) -> None:
    alice = await _user("alice")
    SEEN.clear()
    job_id = await _queue(Actor(alice), "test.ok")
    assert await worker.run_until_empty("w1") == 1
    assert [(alice, {"n": 1, "_project": None})] == SEEN
    job = await _job(job_id)
    assert (job.status, job.attempts, job.created_by) == (JobStatus.DONE, 1, alice)


async def test_rolled_back_change_leaves_no_job(db: None) -> None:
    alice = await _user("alice")

    async def failed_upload() -> None:
        async with transaction(Actor(alice)) as tx:
            await queue.enqueue(tx, queue.NewJob("test.ok"))
            raise RuntimeError("upload failed")

    with pytest.raises(RuntimeError):
        await failed_upload()
    assert await worker.run_until_empty("w1") == 0


async def test_failure_is_retried_later_then_fails(
    db: None, env: Callable[..., None], owner_sql: OwnerSql
) -> None:
    env(MINDGRID_JOB_MAX_ATTEMPTS="2")
    job_id = await _queue(Actor(await _user("alice")), "test.boom")
    assert await worker.run_until_empty("w1") == 1  # retry waits for its backoff
    job = await _job(job_id)
    assert (job.status, job.attempts) == (JobStatus.QUEUED, 1)
    assert "model offline" in job.last_error
    await owner_sql("update jobs set run_after = now()")  # skip the wait
    assert await worker.run_until_empty("w1") == 1
    job = await _job(job_id)
    assert (job.status, job.attempts) == (JobStatus.FAILED, 2)
    assert job.finished_at is not None


async def test_permanent_error_fails_at_once(db: None) -> None:
    job_id = await _queue(Actor(await _user("alice")), "test.bad")
    await worker.run_until_empty("w1")
    job = await _job(job_id)
    assert (job.status, job.attempts, job.last_error) == (
        JobStatus.FAILED,
        1,
        "payload needs a version_id",
    )


async def test_disabled_account_job_fails(db: None) -> None:
    alice = await _user("alice")
    job_id = await _queue(Actor(alice), "test.ok")
    async with transaction(ROOT) as tx:
        await tx.execute(update(User).where(User.id == alice).values(status=UserStatus.DISABLED))
    SEEN.clear()
    await worker.run_until_empty("w1")
    assert SEEN == []
    assert (await _job(job_id)).status == JobStatus.FAILED


async def test_expired_lease_is_claimed_again(db: None, owner_sql: OwnerSql) -> None:
    job_id = await _queue(Actor(await _user("alice")), "test.ok")
    async with transaction(Actor(None)) as tx:
        first = await queue.claim(tx, "w1", ["test.ok"])
    assert first is not None
    await owner_sql("update jobs set locked_until = now() - interval '1 second'")  # w1 died
    async with transaction(Actor(None)) as tx:
        again = await queue.claim(tx, "w2", ["test.ok"])
    assert again is not None
    assert again.attempts == 2
    async with transaction(Actor(None)) as tx:  # the old worker can no longer finish it
        assert await queue.finish(tx, first, "w1", queue.Outcome()) is None
        assert await queue.finish(tx, again, "w2", queue.Outcome()) == "done"
    assert (await _job(job_id)).status == JobStatus.DONE


async def test_jobs_visible_only_to_their_account(db: None) -> None:
    alice, bob = await _user("alice"), await _user("bob")
    await _queue(Actor(alice), "test.ok")
    async with transaction(Actor(bob)) as tx:
        assert (await tx.scalars(select(Job))).all() == []
        tx.add(Job(kind="test.ok", created_by=alice, max_attempts=1))  # cannot forge
        with pytest.raises(Exception, match="row-level security"):
            await tx.flush()


async def _slow(_actor: Actor, _payload: dict[str, Any]) -> None:
    await asyncio.sleep(2.5)


handlers.register("test.slow", _slow)


async def test_long_job_keeps_its_lease(db: None, env: Callable[..., None]) -> None:
    env(MINDGRID_JOB_LEASE_SECONDS="1")  # heartbeat every 1/3 s, job runs 2.5 s
    job_id = await _queue(Actor(await _user("alice")), "test.slow")
    first = asyncio.create_task(worker.run_once("w1"))
    await asyncio.sleep(1.5)  # past the first lease: without the heartbeat w2 would take it
    async with transaction(Actor(None)) as tx:
        assert await queue.claim(tx, "w2", ["test.slow"]) is None
    assert await first
    job = await _job(job_id)
    assert (job.status, job.attempts) == (JobStatus.DONE, 1)
