"""Start a run (checks first, then queued in the same transaction), execute it in the
worker as the account that started it, and read runs back."""

import asyncio
import dataclasses
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.datasets import service as datasets
from mindgrid.db.session import Actor, transaction
from mindgrid.functions.contracts import Frame
from mindgrid.platform.events import service as events
from mindgrid.platform.jobs import handlers, queue
from mindgrid.platform.tenancy import access
from mindgrid.playbooks import catalog, runtime
from mindgrid.playbooks.params import check_inputs, effective
from mindgrid.playbooks.spec import RUNNABLE, PlaybookSpec

from . import events as run_events
from .models import Run, RunStatus

KIND = "runs.execute"


@dataclass(frozen=True, slots=True)
class Start:
    project_id: uuid.UUID
    playbook_id: str
    version: int | None = None
    params: dict[str, Any] = field(default_factory=dict[str, Any])
    inputs: dict[str, Any] = field(default_factory=dict[str, Any])
    callback_url: str | None = None  # receives run.completed / run.failed / job.failed


async def _require_run(tx: AsyncSession, project_id: uuid.UUID) -> None:
    await access.require_project_view(tx, project_id)
    if not await tx.scalar(text("select mindgrid_can_run_in_project(:p)"), {"p": project_id}):
        raise ApiError(403, "run.forbidden", "your role cannot start runs in this project")


async def start(tx: AsyncSession, ask: Start) -> Run:
    await _require_run(tx, ask.project_id)
    eff = (await catalog.overrides(tx, ask.project_id)).get(ask.playbook_id, catalog.Effective())
    if not eff.enabled:
        raise ApiError(409, "playbook.disabled", "this playbook is switched off here")
    spec = catalog.pick(await catalog.all_specs(tx), ask.playbook_id, ask.version, eff.version)
    if spec.status not in RUNNABLE:
        raise ApiError(
            409,
            "playbook.not_runnable",
            "this version cannot run",
            params={"status": spec.status.value},
        )
    params, errors = effective(spec.params, eff.params, ask.params)
    errors += check_inputs(spec.inputs, ask.inputs)
    if errors:
        raise ApiError(
            400, "run.invalid", "the run request has problems", params={"problems": errors[:20]}
        )
    inputs = await _pin_datasets(tx, spec, ask)
    run = Run(
        project_id=ask.project_id,
        playbook_id=spec.id,
        playbook_version=spec.version,
        playbook_status=spec.status.value,
        params=params,
        inputs=inputs,
    )
    tx.add(run)
    await tx.flush()
    payload = {"run_id": str(run.id), "subject": f"runs/{run.id}"}
    await queue.enqueue(tx, queue.NewJob(KIND, payload, ask.project_id))
    if ask.callback_url:
        await events.register_callback(
            tx, f"runs/{run.id}", ask.project_id, ask.callback_url, run_events.OUTCOMES
        )
    await tx.refresh(run)
    return run


async def _pin_datasets(tx: AsyncSession, spec: PlaybookSpec, ask: Start) -> dict[str, Any]:
    """Dataset inputs (given, else the spec default) become {"dataset": name, "version": n}:
    the run uses that version. An optional dataset that does not exist is left out."""
    pinned = dict(ask.inputs)
    for name, s in spec.inputs.items():
        given = pinned.get(name, s.default)
        if s.type != "dataset" or given is None:
            continue
        ref: dict[str, Any] = {"dataset": given} if isinstance(given, str) else dict(given)
        try:
            found = await datasets.by_name(tx, ask.project_id, str(ref["dataset"]))
        except ApiError:
            if s.required:
                raise
            pinned.pop(name, None)
            continue
        if found.current_version == 0:
            raise ApiError(
                409, "dataset.empty", "the dataset has no version yet", params={"name": found.name}
            )
        version = int(ref.get("version") or found.current_version)
        pinned[name] = {"dataset": found.name, "version": version}
    return pinned


async def _frames(tx: AsyncSession, run: Run, spec: PlaybookSpec) -> dict[str, Any]:
    loaded = dict(run.inputs)
    for name, s in spec.inputs.items():
        if s.type == "dataset" and name in loaded:
            ref = loaded[name]
            dataset = await datasets.by_name(tx, run.project_id, ref["dataset"])
            version, raw = await datasets.load_raw(tx, dataset, int(ref["version"]))
            loaded[name] = Frame(
                dataset.name,
                version.version,
                raw,
                version.media_type,
                dict(version.meta),
                records_path=version.records_path,
            )
    return loaded


async def _execute(actor: Actor, payload: dict[str, Any]) -> None:
    run_id = uuid.UUID(str(payload.get("run_id", "")))
    async with transaction(actor) as tx:
        run = await tx.get(Run, run_id)
        if run is None or run.status in {RunStatus.DONE, RunStatus.FAILED}:
            return  # finished already (a retry after a lost lease runs it again)
        specs = await catalog.all_specs(tx)
        spec = specs.get((run.playbook_id, run.playbook_version))
        if spec is None:
            raise handlers.PermanentJobError("the playbook version is gone")
        run.status = RunStatus.RUNNING
        inputs, params = await _frames(tx, run, spec), dict(run.params)
    result = await asyncio.to_thread(runtime.execute, spec, inputs, params)
    async with transaction(actor) as tx:
        run = await tx.get(Run, run_id)
        if run is None:
            return
        run.status = RunStatus.DONE if result.ok else RunStatus.FAILED
        run.outputs, run.error = result.outputs, result.error
        run.steps = [dataclasses.asdict(s) for s in result.steps]
        run.finished_at = datetime.now(UTC)
        await _announce(tx, run)


async def _announce(tx: AsyncSession, run: Run) -> None:
    data = run_events.RunFinished(
        run_id=str(run.id),
        playbook_id=run.playbook_id,
        playbook_version=run.playbook_version,
        playbook_status=run.playbook_status,
        status=run.status.value,
        error=run.error[:500],
        outputs=sorted(run.outputs),
        links=events.link(
            f"/v1/runs/{run.id}", f"/projects/{run.project_id}?tab=runs&run={run.id}"
        ),
    )
    await events.emit(tx, data, project_id=run.project_id, subject=f"runs/{run.id}")


async def get(tx: AsyncSession, run_id: uuid.UUID) -> Run:
    run = await tx.get(Run, run_id)
    if run is None:
        raise ApiError(404, "run.not_found", "run not found")
    return run


async def page(tx: AsyncSession, project_id: uuid.UUID, limit: int = 50) -> list[Run]:
    await access.require_project_view(tx, project_id)
    query = (
        select(Run).where(Run.project_id == project_id).order_by(Run.created_at.desc()).limit(limit)
    )
    return list((await tx.scalars(query)).all())


handlers.register(KIND, _execute)
