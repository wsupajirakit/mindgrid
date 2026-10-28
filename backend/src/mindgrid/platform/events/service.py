"""Record events (inside the caller's transaction), register one-shot callbacks, manage
subscriptions (the secret is shown once, stored sealed), list deliveries, replay, ping."""

import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core import netguard
from mindgrid.core.errors import ApiError
from mindgrid.platform.secrets import crypto
from mindgrid.platform.tenancy import access

from . import config as event_config
from . import signing, types
from .models import EventCallback, EventDelivery, EventSubscription

PATTERN = r"^(\*|[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*(\.\*)?)$"


def link(api_path: str, ui_path: str) -> types.Links:
    base = event_config.get_settings().public_url.rstrip("/")
    return types.Links(api=base + api_path, ui=base + ui_path)


async def emit(
    tx: AsyncSession, data: types.EventData, *, project_id: uuid.UUID | None, subject: str
) -> uuid.UUID:
    """Record one event; its deliveries are created by the database in the same commit."""
    declared = next((t for t in types.catalog_types() if t.data is type(data)), None)
    if declared is None:
        raise ValueError(f"{type(data).__name__} is not a declared event type")
    body = data.model_dump(mode="json")
    if len(json.dumps(body)) > event_config.get_settings().max_data_bytes:
        raise ValueError(f"event data for {declared.name} is too large: link to it instead")
    found = await tx.scalar(
        text("select mindgrid_emit_event(:type, :project, :subject, cast(:data as jsonb))"),
        {
            "type": declared.name,
            "project": project_id,
            "subject": subject,
            "data": json.dumps(body),
        },
    )
    return uuid.UUID(str(found))


async def check_url(url: str) -> None:
    try:
        await netguard.check(url)
    except netguard.BlockedTargetError as err:
        raise ApiError(400, "event.bad_url", str(err)) from err


async def register_callback(
    tx: AsyncSession, subject: str, project_id: uuid.UUID | None, url: str, outcomes: list[str]
) -> None:
    """Deliver the first event about `subject` whose type is in `outcomes` to `url`."""
    await check_url(url)
    tx.add(EventCallback(subject=subject, project_id=project_id, url=url, event_types=outcomes))
    await tx.flush()


@dataclass(frozen=True, slots=True)
class NewSubscription:
    name: str
    url: str
    event_types: list[str]
    project_id: uuid.UUID | None = None  # None = every project (superadmin only)


def _binding(sub_id: uuid.UUID) -> str:
    return f"event-subscription:{sub_id}"


async def _allowed(tx: AsyncSession, project_id: uuid.UUID | None, superadmin: bool) -> None:
    if project_id is None:
        if not superadmin:
            raise ApiError(403, "auth.superadmin_only", "superadmin only")
        return
    await access.require_project_manage(tx, project_id)


async def subscribe(
    tx: AsyncSession, new: NewSubscription, superadmin: bool
) -> tuple[EventSubscription, str]:
    """(subscription, secret): the secret is returned this once and never again."""
    await _allowed(tx, new.project_id, superadmin)
    await check_url(new.url)
    unknown = [t for t in new.event_types if not t.endswith("*") and types.get(t) is None]
    if unknown or not new.event_types:
        raise ApiError(400, "event.unknown_type", "unknown event type", params={"types": unknown})
    sub_id = uuid.uuid7()
    secret = signing.new_secret()
    sealed = crypto.seal(secret, _binding(sub_id))
    row = EventSubscription(
        id=sub_id,
        project_id=new.project_id,
        name=new.name,
        url=new.url,
        event_types=new.event_types,
        secret_ciphertext=sealed.ciphertext,
        secret_nonce=sealed.nonce,
        secret_version=sealed.version,
    )
    tx.add(row)
    await tx.flush()
    await tx.refresh(row)
    return row, secret


def open_secret(sub_id: uuid.UUID, ciphertext: bytes, nonce: bytes, version: int) -> str:
    return crypto.open_sealed(crypto.Sealed(ciphertext, nonce, version), _binding(sub_id))


async def subscriptions(
    tx: AsyncSession, project_id: uuid.UUID | None, superadmin: bool
) -> list[EventSubscription]:
    await _allowed(tx, project_id, superadmin)
    query = select(EventSubscription).where(
        EventSubscription.project_id.is_(None)
        if project_id is None
        else EventSubscription.project_id == project_id
    )
    return list((await tx.scalars(query.order_by(EventSubscription.name))).all())


async def set_enabled(tx: AsyncSession, sub_id: uuid.UUID, enabled: bool, superadmin: bool) -> None:
    row = await tx.get(EventSubscription, sub_id)
    if row is None:
        raise ApiError(404, "event.subscription_not_found", "subscription not found")
    await _allowed(tx, row.project_id, superadmin)
    row.enabled, row.dead_in_a_row = enabled, 0
    row.disabled_reason = "" if enabled else "switched off"


async def unsubscribe(tx: AsyncSession, sub_id: uuid.UUID, superadmin: bool) -> None:
    row = await tx.get(EventSubscription, sub_id)
    if row is None:
        raise ApiError(404, "event.subscription_not_found", "subscription not found")
    await _allowed(tx, row.project_id, superadmin)
    await tx.execute(delete(EventSubscription).where(EventSubscription.id == sub_id))


async def ping(tx: AsyncSession, sub_id: uuid.UUID) -> uuid.UUID:
    data = types.Ping(subscription_id=str(sub_id), message="test")
    found = await tx.scalar(
        text("select mindgrid_ping_subscription(:sub, cast(:data as jsonb))"),
        {"sub": sub_id, "data": data.model_dump_json()},
    )
    if found is None:
        raise ApiError(404, "event.subscription_not_found", "subscription not found")
    return uuid.UUID(str(found))


async def replay(tx: AsyncSession, delivery_id: uuid.UUID) -> None:
    if not await tx.scalar(text("select mindgrid_replay_delivery(:id)"), {"id": delivery_id}):
        raise ApiError(404, "event.delivery_not_found", "delivery not found")


async def deliveries(
    tx: AsyncSession,
    *,
    subscription_id: uuid.UUID | None = None,
    event_id: uuid.UUID | None = None,
    limit: int = 100,
) -> list[EventDelivery]:
    query = select(EventDelivery).order_by(EventDelivery.created_at.desc()).limit(limit)
    if subscription_id is not None:
        query = query.where(EventDelivery.subscription_id == subscription_id)
    if event_id is not None:
        query = query.where(EventDelivery.event_id == event_id)
    return list((await tx.scalars(query)).all())


def envelope(event: dict[str, Any]) -> dict[str, Any]:
    """The CloudEvents 1.0 structured form of an event."""
    base = event_config.get_settings().public_url.rstrip("/")
    project = event.get("project_id")
    source = f"{base}/v1/projects/{project}" if project else f"{base}/v1/system"
    return {
        "specversion": "1.0",
        "id": str(event["event_id"]),
        "source": source,
        "type": event["event_type"],
        "subject": event["subject"],
        "time": event["event_time"].isoformat(),
        "datacontenttype": "application/json",
        "dataschema": f"{base}/v1/events/types/{event['event_type']}",
        "data": event["data"],
    }
