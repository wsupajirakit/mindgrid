"""Event pipeline end to end against local receivers: fan-out by type and project, signed
deliveries, one-shot callbacks, retry then dead, 410 switches a subscription off, a slow
receiver does not hold up a fast one, replay and ping."""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import pytest

from mindgrid.datasets import events as dataset_events
from mindgrid.db.session import Actor, transaction
from mindgrid.platform.events import deliver, service, signing
from mindgrid.platform.events.models import DeliveryStatus, EventSubscription
from mindgrid.platform.identity import users
from mindgrid.platform.tenancy import projects
from mindgrid.platform.tenancy.schemas import ProjectInput
from mindgrid.runs.events import RunFinished

pytestmark = [pytest.mark.anyio, pytest.mark.db]
ROOT = Actor(None, superadmin=True)


class Receiver:
    """A local HTTP receiver answering with a fixed status (after an optional delay)."""

    def __init__(self, status: int = 200, delay: float = 0) -> None:
        self.status, self.delay = status, delay
        self.got: list[tuple[dict[str, str], bytes]] = []
        self.url = ""

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        head = (await reader.readuntil(b"\r\n\r\n")).decode()
        lines = head.split("\r\n")
        headers = {
            k.lower(): v.strip() for k, _, v in (ln.partition(":") for ln in lines[1:] if ln)
        }
        body = await reader.readexactly(int(headers.get("content-length", "0")))
        await asyncio.sleep(self.delay)
        self.got.append((headers, body))
        writer.write(
            f"HTTP/1.1 {self.status} X\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".encode()
        )
        await writer.drain()
        writer.close()


@pytest.fixture
async def receivers(env: Callable[..., None]) -> AsyncIterator[Callable[..., Awaitable[Receiver]]]:
    env(MINDGRID_OUTBOUND_ALLOW_PRIVATE_HOSTS="127.0.0.1", MINDGRID_EVENT_RETRY_SECONDS="0,0")
    servers: list[asyncio.Server] = []

    async def make(status: int = 200, delay: float = 0) -> Receiver:
        r = Receiver(status, delay)
        server = await asyncio.start_server(r.handle, "127.0.0.1", 0)
        servers.append(server)
        r.url = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}/hook"
        return r

    yield make
    for server in servers:
        server.close()


async def _setup() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    async with transaction(ROOT) as tx:
        alice = (
            await users.create_user(
                tx, email="a@example.com", display_name="a", password="Test-pass-1"
            )
        ).id
    async with transaction(Actor(alice)) as tx:
        p1 = (await projects.create_project(tx, alice, ProjectInput(slug="p1", name="P1"))).id
        p2 = (await projects.create_project(tx, alice, ProjectInput(slug="p2", name="P2"))).id
    return alice, p1, p2


def _run_event(run: str = "r1", status: str = "done") -> RunFinished:
    return RunFinished(
        run_id=run,
        playbook_id="core.table-screen",
        playbook_version=1,
        playbook_status="active",
        status=status,
        error="",
        outputs=["rows"],
        links=service.link(f"/v1/runs/{run}", f"/projects/x?tab=runs&run={run}"),
    )


async def _subscribe(
    alice: uuid.UUID, pid: uuid.UUID, url: str, types: list[str]
) -> tuple[uuid.UUID, str]:
    async with transaction(Actor(alice)) as tx:
        row, secret = await service.subscribe(
            tx, service.NewSubscription("s", url, types, pid), False
        )
        return row.id, secret


async def _emit(alice: uuid.UUID, pid: uuid.UUID, data: Any, subject: str = "runs/r1") -> None:
    async with transaction(Actor(alice)) as tx:
        await service.emit(tx, data, project_id=pid, subject=subject)


async def _drain() -> None:
    for _ in range(5):
        await deliver.run_once("w-test")


async def test_fan_out_by_type_and_project_signed(db: None, receivers: Any) -> None:
    alice, p1, p2 = await _setup()
    runs_rx, other_rx, p2_rx = await receivers(), await receivers(), await receivers()
    _, secret = await _subscribe(alice, p1, runs_rx.url, ["run.*"])
    await _subscribe(alice, p1, other_rx.url, [dataset_events.DATASET_UPDATED.name])
    await _subscribe(alice, p2, p2_rx.url, ["*"])
    await _emit(alice, p1, _run_event())
    await _drain()
    assert len(runs_rx.got) == 1
    assert other_rx.got == []
    assert p2_rx.got == []
    headers, body = runs_rx.got[0]
    assert headers["content-type"].startswith("application/cloudevents+json")
    assert signing.verify_v1(
        secret,
        headers["webhook-id"],
        int(headers["webhook-timestamp"]),
        body,
        headers["webhook-signature"],
    )
    assert "v1a," in headers["webhook-signature"]
    event = json.loads(body)
    assert (event["type"], event["subject"], event["data"]["run_id"]) == (
        "run.completed",
        "runs/r1",
        "r1",
    )


async def test_callback_is_one_shot(db: None, receivers: Any) -> None:
    alice, p1, _ = await _setup()
    rx = await receivers()
    async with transaction(Actor(alice)) as tx:
        await service.register_callback(tx, "runs/r9", p1, rx.url, ["run.completed"])
    await _emit(alice, p1, _run_event("r9"), subject="runs/r9")
    await _emit(alice, p1, _run_event("r9"), subject="runs/r9")
    await _drain()
    assert len(rx.got) == 1


async def test_retry_then_dead_and_gone_switches_off(db: None, receivers: Any) -> None:
    alice, p1, _ = await _setup()
    failing, gone = await receivers(500), await receivers(410)
    fail_id, _ = await _subscribe(alice, p1, failing.url, ["run.completed"])
    gone_id, _ = await _subscribe(alice, p1, gone.url, ["run.completed"])
    await _emit(alice, p1, _run_event())
    await _drain()
    assert len(failing.got) == 3  # first try + 2 retries (schedule "0,0"), then dead
    assert len(gone.got) == 1
    async with transaction(Actor(alice)) as tx:
        states = {d.subscription_id: d.status for d in await service.deliveries(tx)}
        gone_row = await tx.get(EventSubscription, gone_id)
    assert states[fail_id] is DeliveryStatus.DEAD
    assert states[gone_id] is DeliveryStatus.DEAD
    assert gone_row is not None
    assert not gone_row.enabled
    assert "410" in gone_row.disabled_reason


async def test_slow_receiver_does_not_block_another(db: None, receivers: Any) -> None:
    alice, p1, _ = await _setup()
    slow, fast = await receivers(delay=0.5), await receivers()
    await _subscribe(alice, p1, slow.url, ["run.completed"])
    await _subscribe(alice, p1, fast.url, ["run.completed"])
    for i in range(3):
        await _emit(alice, p1, _run_event(f"r{i}"), subject=f"runs/r{i}")
    claimed = await deliver.run_once("w-test")
    assert claimed == 2  # one in flight per subscription
    assert len(fast.got) == 1
    assert len(slow.got) == 1
    await _drain()
    assert len(fast.got) == 3
    assert len(slow.got) == 3


async def test_replay_and_ping(db: None, receivers: Any) -> None:
    alice, p1, _ = await _setup()
    rx = await receivers()
    sub_id, _ = await _subscribe(alice, p1, rx.url, ["run.completed"])
    async with transaction(Actor(alice)) as tx:
        await service.ping(tx, sub_id)
    await _drain()
    assert json.loads(rx.got[0][1])["type"] == "subscription.test"
    async with transaction(Actor(alice)) as tx:
        delivery = (await service.deliveries(tx, subscription_id=sub_id))[0]
        await service.replay(tx, delivery.id)
    await _drain()
    assert len(rx.got) == 2
