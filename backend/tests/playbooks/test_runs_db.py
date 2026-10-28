"""Runs end to end: start (checks, queue) -> worker -> outputs; switching off and
parameter overrides per project; who may start runs; custom specs and immutable versions."""

import uuid

import pytest
from sqlalchemy import select

from mindgrid.core.errors import ApiError
from mindgrid.core.settings_registry import Scope
from mindgrid.db.session import Actor, transaction
from mindgrid.platform.identity import users
from mindgrid.platform.jobs import worker
from mindgrid.platform.tenancy import members, projects
from mindgrid.platform.tenancy.models import ProjectRole
from mindgrid.platform.tenancy.schemas import ProjectInput
from mindgrid.playbooks import catalog, overrides, shipped
from mindgrid.runs import service as runs
from mindgrid.runs.models import Run, RunStatus

pytestmark = [pytest.mark.anyio, pytest.mark.db]
ROOT = Actor(None, superadmin=True)
ROWS = [{"name": "a", "score": 3}, {"name": "b", "score": 9}]
SCREEN = "core.table-screen"


async def _setup() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    async with transaction(ROOT) as tx:
        alice, bob = [
            (
                await users.create_user(
                    tx, email=f"{n}@example.com", display_name=n, password="Test-pass-1"
                )
            ).id
            for n in ("alice", "bob")
        ]
    async with transaction(Actor(alice)) as tx:
        pid = (await projects.create_project(tx, alice, ProjectInput(slug="p", name="P"))).id
        await members.set_member(tx, pid, bob, ProjectRole.VIEWER)
        # A playbook is off for a project until it is added there.
        await overrides.put(tx, (Scope.PROJECT, pid), SCREEN, overrides.Change(), False)
    return alice, bob, pid


async def _start(actor: Actor, pid: uuid.UUID, **params: object) -> uuid.UUID:
    async with transaction(actor) as tx:
        run = await runs.start(
            tx, runs.Start(pid, SCREEN, params=dict(params), inputs={"rows": ROWS})
        )
        return run.id


async def _run(run_id: uuid.UUID, actor: Actor) -> Run:
    await worker.run_until_empty("w1")
    async with transaction(actor) as tx:
        return await runs.get(tx, run_id)


async def test_run_executes_in_the_worker(db: None) -> None:
    alice, bob, pid = await _setup()
    run = await _run(await _start(Actor(alice), pid, top_n=1), Actor(bob))  # viewer reads
    assert run.status is RunStatus.DONE
    assert run.outputs["rows"] == [{"name": "b", "score": 9}]
    assert (run.playbook_version, run.params["top_n"]) == (1, 1)
    with pytest.raises(ApiError) as err:  # a viewer may read runs, not start them
        await _start(Actor(bob), pid)
    assert err.value.code == "run.forbidden"


async def test_project_override_switches_off_and_sets_params(db: None) -> None:
    alice, _bob, pid = await _setup()
    target = (Scope.PROJECT, pid)
    async with transaction(Actor(alice)) as tx:
        await overrides.put(tx, target, SCREEN, overrides.Change(params={"minimum": 5}), False)
    run = await _run(await _start(Actor(alice), pid), Actor(alice))
    assert run.outputs["matched"] == 1  # only score 9 >= 5
    async with transaction(Actor(alice)) as tx:
        await overrides.put(tx, target, SCREEN, overrides.Change(enabled=False), False)
        listed = {p["id"]: p for p in await catalog.summaries(tx, pid)}
    assert listed[SCREEN]["enabled"] is False
    with pytest.raises(ApiError) as err:
        await _start(Actor(alice), pid)
    assert err.value.code == "playbook.disabled"
    with pytest.raises(ApiError):  # a bad override value is refused up front
        async with transaction(Actor(alice)) as tx:
            await overrides.put(tx, target, SCREEN, overrides.Change(params={"top_n": 0}), False)


async def test_custom_specs_are_superadmin_only_and_versions_immutable(db: None) -> None:
    alice, _bob, pid = await _setup()
    base = shipped.all_specs()[(SCREEN, 1)]
    newer = base.model_copy(update={"version": 2, "title": "Screen v2"})
    async with transaction(ROOT) as tx:
        await catalog.add_custom(tx, newer)
    with pytest.raises(ApiError) as err:
        async with transaction(ROOT) as tx:
            await catalog.add_custom(tx, newer)
    assert err.value.code == "playbook.version_exists"
    with pytest.raises(Exception, match="row-level security"):
        async with transaction(Actor(alice)) as tx:
            await catalog.add_custom(tx, base.model_copy(update={"version": 3}))
    run = await _run(await _start(Actor(alice), pid), Actor(alice))
    assert run.playbook_version == 2  # newest runnable version by default
    async with transaction(Actor(alice)) as tx:
        assert len((await tx.scalars(select(Run))).all()) == 1
