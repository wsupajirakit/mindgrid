"""Connectors: create and change (project managers), sync now or on schedule. A sync
fetches each resource and adds a dataset version when the bytes changed; it runs in the
worker as the account that set the connector up."""

import functools
import json
import uuid
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.core.settings_registry import Scope
from mindgrid.datasets import service as datasets
from mindgrid.db.session import SYSTEM, Actor, transaction
from mindgrid.platform.events import service as events
from mindgrid.platform.jobs import handlers, queue
from mindgrid.platform.secrets import service as secrets
from mindgrid.platform.tenancy import access

from . import config as connector_config
from . import events as connector_events
from .fetch import FetchError, fetch
from .models import Connector
from .spec import ConnectorSpec

KIND = "connectors.sync"
MEDIA = datasets.MEDIA


@functools.cache
def templates() -> list[dict[str, Any]]:
    folder = files("mindgrid.bridges.connectors.templates")
    found = [
        json.loads(f.read_text(encoding="utf-8"))
        for f in sorted(folder.iterdir(), key=lambda f: f.name)
        if f.name.endswith(".json")
    ]
    for item in found:
        ConnectorSpec.model_validate(item["spec"])  # a broken template fails at start-up
    return found


def _schedule(every: int | None) -> datetime | None:
    if every is None:
        return None
    if every < connector_config.get_settings().min_every_minutes:
        raise ApiError(
            400,
            "connector.too_often",
            "schedule interval too short",
            params={"min": connector_config.get_settings().min_every_minutes},
        )
    return datetime.now(UTC) + timedelta(minutes=every)


async def save(
    tx: AsyncSession,
    project_id: uuid.UUID,
    name: str,
    spec: ConnectorSpec,
    every_minutes: int | None,
) -> Connector:
    await access.require_project_manage(tx, project_id)
    row = await tx.scalar(
        select(Connector).where(Connector.project_id == project_id, Connector.name == name)
    )
    if row is None:
        row = Connector(project_id=project_id, name=name)
        tx.add(row)
    row.spec = spec.model_dump(mode="json")
    row.every_minutes, row.next_run_at = every_minutes, _schedule(every_minutes)
    await tx.flush()
    await tx.refresh(row)
    return row


async def listing(tx: AsyncSession, project_id: uuid.UUID) -> list[Connector]:
    await access.require_project_manage(tx, project_id)
    query = select(Connector).where(Connector.project_id == project_id).order_by(Connector.name)
    return list((await tx.scalars(query)).all())


async def get(tx: AsyncSession, connector_id: uuid.UUID) -> Connector:
    row = await tx.get(Connector, connector_id)
    if row is None:
        raise ApiError(404, "connector.not_found", "connector not found")
    await access.require_project_manage(tx, row.project_id)
    return row


async def request_sync(
    tx: AsyncSession, connector_id: uuid.UUID, callback_url: str | None = None
) -> None:
    row = await get(tx, connector_id)
    if callback_url:
        await events.register_callback(
            tx, f"connectors/{row.id}", row.project_id, callback_url, connector_events.OUTCOMES
        )
    payload = {"connector_id": str(row.id), "subject": f"connectors/{row.id}"}
    await queue.enqueue(tx, queue.NewJob(KIND, payload, row.project_id))


async def _secret(tx: AsyncSession, row: Connector, spec: ConnectorSpec) -> str:
    if spec.auth.type == "none":
        return ""
    value = await secrets.reveal(tx, Scope.PROJECT, row.project_id, spec.auth.secret)
    if value is None:
        raise handlers.PermanentJobError(f"project secret {spec.auth.secret!r} is not set")
    return value


async def _sync(actor: Actor, payload: dict[str, Any]) -> None:
    connector_id = uuid.UUID(str(payload.get("connector_id", "")))
    async with transaction(actor) as tx:
        row = await get(tx, connector_id)
        spec = ConnectorSpec.model_validate(row.spec)
        secret = await _secret(tx, row, spec)
        project_id = row.project_id
    changed: list[str] = []
    error = ""
    for resource in spec.resources:
        try:
            data = await fetch(spec, resource, secret)
        except (FetchError, OSError) as err:
            error = str(err)[:500]
            break
        async with transaction(actor) as tx:
            dataset = await datasets.ensure(
                tx, project_id, resource.dataset, f"connector:{connector_id}", resource.title
            )
            incoming = datasets.Incoming(data, MEDIA[resource.format], resource.records_path)
            _, created = await datasets.add_version(tx, dataset, incoming)
            if created:
                changed.append(resource.dataset)
    async with transaction(actor) as tx:
        row = await get(tx, connector_id)
        row.last_run_at, row.last_status = datetime.now(UTC), "failed" if error else "ok"
        row.last_error, row.last_changed = error, changed
        if not error:
            data = connector_events.ConnectorSynced(
                connector_id=str(row.id),
                name=row.name,
                changed=changed,
                links=events.link(
                    f"/v1/projects/{row.project_id}/connectors",
                    f"/projects/{row.project_id}?tab=connectors",
                ),
            )
            await events.emit(tx, data, project_id=row.project_id, subject=f"connectors/{row.id}")
    if error:
        raise RuntimeError(error)  # retried with backoff by the queue


async def _enqueue_due() -> None:
    async with transaction(SYSTEM) as tx:
        await tx.execute(text("select mindgrid_enqueue_due_syncs()"))


handlers.register(KIND, _sync)
handlers.every("connectors.schedule", 60, _enqueue_due)
