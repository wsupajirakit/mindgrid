"""A generic connector against a local HTTP server: bearer auth from a project secret,
datasets versioned only when the bytes change, schedules queued by the database, and a
playbook reading the dataset with its version pinned in the run."""

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from sqlalchemy import func, select, text

from mindgrid.bridges.connectors import service as connectors
from mindgrid.bridges.connectors.spec import ConnectorSpec
from mindgrid.core.settings_registry import Scope
from mindgrid.datasets import service as datasets
from mindgrid.db.session import SYSTEM, Actor, transaction
from mindgrid.platform.identity import users
from mindgrid.platform.jobs import worker
from mindgrid.platform.jobs.models import Job
from mindgrid.platform.secrets import service as secrets
from mindgrid.platform.tenancy import categories, projects
from mindgrid.platform.tenancy.schemas import ProjectInput
from mindgrid.playbooks import overrides
from mindgrid.runs import service as runs

pytestmark = [pytest.mark.anyio, pytest.mark.db]
ROOT = Actor(None, superadmin=True)
ORIGINAL = b"# data_asof_utc: 2026-10-23T21:00:00Z\nname,score\na,3\nb,9\nc,5\n"
BODY = {"v": b"# data_asof_utc: 2026-10-23T21:00:00Z\nname,score\na,3\nb,9\nc,5\n"}


async def _serve(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    head = (await reader.readuntil(b"\r\n\r\n")).decode()
    ok = "authorization: bearer s3cret" in head.lower() and "interval=1d" in head
    body = BODY["v"] if ok else b"no"
    status = b"200 OK" if ok else b"401 Unauthorized"
    writer.write(
        b"HTTP/1.1 "
        + status
        + b"\r\nContent-Type: text/csv\r\n"
        + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
        + body
    )
    await writer.drain()
    writer.close()


@pytest.fixture
async def source(env: Callable[..., None]) -> AsyncIterator[str]:
    BODY["v"] = ORIGINAL
    server = await asyncio.start_server(_serve, "127.0.0.1", 0)
    env(MINDGRID_OUTBOUND_ALLOW_PRIVATE_HOSTS="127.0.0.1")
    yield f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}"
    server.close()
    await server.wait_closed()


async def _setup(base_url: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    async with transaction(ROOT) as tx:
        alice = (
            await users.create_user(
                tx, email="a@example.com", display_name="a", password="Test-pass-1"
            )
        ).id
    spec = ConnectorSpec.model_validate(
        {
            "base_url": base_url,
            "auth": {"type": "bearer", "secret": "connector.src.token"},
            "resources": [
                {"dataset": "scores", "path": "/api/export", "query": {"interval": "1d"}}
            ],
        }
    )
    async with transaction(Actor(alice)) as tx:
        pid = (await projects.create_project(tx, alice, ProjectInput(slug="p", name="P"))).id
        await secrets.put(tx, Scope.PROJECT, pid, "connector.src.token", "s3cret")
        cid = (await connectors.save(tx, pid, "src", spec, every_minutes=60)).id
    return alice, pid, cid


async def _sync(actor: Actor, cid: uuid.UUID) -> list[str]:
    async with transaction(actor) as tx:
        await connectors.request_sync(tx, cid)
    await worker.run_until_empty("w1")
    async with transaction(actor) as tx:
        row = await connectors.get(tx, cid)
        assert row.last_status == "ok", row.last_error
        return list(row.last_changed)


async def test_sync_versions_only_changed_bytes(db: None, source: str) -> None:
    alice, pid, cid = await _setup(source)
    assert await _sync(Actor(alice), cid) == ["scores"]
    assert await _sync(Actor(alice), cid) == []  # same bytes: no new version
    BODY["v"] = BODY["v"] + b"d,7\n"
    assert await _sync(Actor(alice), cid) == ["scores"]
    async with transaction(Actor(alice)) as tx:
        found = await datasets.by_name(tx, pid, "scores")
        newest, parsed = await datasets.load(tx, found)
    assert (newest.version, newest.rows) == (2, 4)
    assert newest.meta["data_asof_utc"] == "2026-10-23T21:00:00Z"
    assert parsed.rows[-1] == {"name": "d", "score": 7}


async def test_due_schedules_become_jobs(
    db: None, source: str, owner_sql: Callable[[str], Awaitable[None]]
) -> None:
    _alice, _pid, _cid = await _setup(source)
    await owner_sql("update connectors set next_run_at = now() - interval '1 minute'")
    async with transaction(SYSTEM) as tx:
        queued = await tx.scalar(text("select mindgrid_enqueue_due_syncs()"))
    assert queued == 1
    async with transaction(ROOT) as tx:
        assert await tx.scalar(select(func.count()).select_from(Job)) == 1


async def test_playbook_reads_a_pinned_dataset_version(db: None, source: str) -> None:
    """A project with no knowledge at all (no category) still runs playbooks on synced data."""
    alice, pid, cid = await _setup(source)
    async with transaction(Actor(alice)) as tx:
        assert await categories.list_categories(tx, pid) == []
    await _sync(Actor(alice), cid)
    async with transaction(Actor(alice)) as tx:
        change = overrides.Change()  # playbooks are off for a project until added
        await overrides.put(tx, (Scope.PROJECT, pid), "core.dataset-screen", change, False)
        run = await runs.start(
            tx,
            runs.Start(
                pid, "core.dataset-screen", params={"minimum": 4}, inputs={"data": "scores"}
            ),
        )
    assert run.inputs == {"data": {"dataset": "scores", "version": 1}}
    await worker.run_until_empty("w1")
    async with transaction(Actor(alice)) as tx:
        done = await runs.get(tx, run.id)
    assert done.error == ""
    assert [r["name"] for r in done.outputs["rows"]] == ["b", "c"]


async def test_a_json_dataset_keeps_where_its_records_are(db: None) -> None:
    """Reading a JSON version later (for a run) uses the records path it was synced with."""
    async with transaction(ROOT) as tx:
        alice = (
            await users.create_user(
                tx, email="j@example.com", display_name="j", password="Test-pass-1"
            )
        ).id
    async with transaction(Actor(alice)) as tx:
        pid = (await projects.create_project(tx, alice, ProjectInput(slug="j", name="J"))).id
        dataset = await datasets.ensure(tx, pid, "forecast", "upload")
        body = b'{"lat": 13.7, "daily": {"time": ["d1", "d2"], "t_max": [33.1, 34.0]}}'
        await datasets.add_version(
            tx, dataset, datasets.Incoming(body, "application/json", "daily")
        )
        _, parsed = await datasets.load(tx, dataset)
    assert parsed.rows == [{"time": "d1", "t_max": 33.1}, {"time": "d2", "t_max": 34.0}]


async def test_a_playbook_reads_a_json_dataset_through_its_records_path(db: None) -> None:
    """The run's frame parses the pinned JSON version with the path it was synced with."""
    async with transaction(ROOT) as tx:
        alice = (
            await users.create_user(
                tx, email="r@example.com", display_name="r", password="Test-pass-1"
            )
        ).id
    async with transaction(Actor(alice)) as tx:
        pid = (await projects.create_project(tx, alice, ProjectInput(slug="r", name="R"))).id
        dataset = await datasets.ensure(tx, pid, "forecast", "upload")
        body = b'{"daily": {"name": ["a", "b", "c"], "score": [1, 5, 9]}}'
        await datasets.add_version(
            tx, dataset, datasets.Incoming(body, "application/json", "daily")
        )
        change = overrides.Change()
        await overrides.put(tx, (Scope.PROJECT, pid), "core.dataset-screen", change, False)
        run = await runs.start(
            tx,
            runs.Start(
                pid, "core.dataset-screen", params={"minimum": 4}, inputs={"data": "forecast"}
            ),
        )
    await worker.run_until_empty("w1")
    async with transaction(Actor(alice)) as tx:
        done = await runs.get(tx, run.id)
    assert done.error == ""
    assert [r["name"] for r in done.outputs["rows"]] == ["c", "b"]
