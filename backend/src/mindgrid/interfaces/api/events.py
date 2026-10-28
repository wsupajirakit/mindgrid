"""/v1/events: the public contract (event types with JSON Schema, the server's signing
key) and, for project managers and superadmins, subscriptions, the event log, deliveries,
replay and test pings."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from mindgrid.core.errors import ApiError
from mindgrid.platform.events import service as events
from mindgrid.platform.events import signing, types
from mindgrid.platform.events.models import Event, EventDelivery, EventSubscription
from mindgrid.platform.jobs import events as _job_events  # defines job.failed

from .deps import CurrentPrincipal, Tx

router = APIRouter(tags=["events"])
JOB_FAILED = _job_events.JOB_FAILED.name


class SubscriptionIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=8, max_length=2000)
    event_types: list[str] = Field(
        min_length=1, max_length=50, description='Exact types, "area.*" or "*".'
    )


class SubscriptionOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID | None
    name: str
    url: str
    event_types: list[str]
    enabled: bool
    dead_in_a_row: int
    disabled_reason: str
    created_at: datetime

    @classmethod
    def of(cls, s: EventSubscription) -> SubscriptionOut:
        return cls.model_validate(s, from_attributes=True)


class CreatedOut(BaseModel):
    subscription: SubscriptionOut
    secret: str = Field(description="Shown once: verify the v1 signature with it.")


class EventOut(BaseModel):
    id: uuid.UUID
    type: str
    subject: str
    data: dict[str, Any]
    created_at: datetime


class DeliveryOut(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    subscription_id: uuid.UUID | None
    url: str
    status: str
    attempts: int
    next_attempt_at: datetime
    last_status_code: int | None
    last_error: str
    delivered_at: datetime | None

    @classmethod
    def of(cls, d: EventDelivery) -> DeliveryOut:
        return cls.model_validate(d, from_attributes=True)


class EnabledIn(BaseModel):
    enabled: bool


@router.get("/events/types")
def event_types() -> list[dict[str, Any]]:
    return types.catalog()


@router.get("/events/types/{event_type}")
def event_type(event_type: str) -> dict[str, Any]:
    found = types.get(event_type)
    if found is None:
        raise ApiError(
            404, "event.unknown_type", "unknown event type", params={"types": [event_type]}
        )
    return {"type": found.name, "summary": found.summary, "data": found.data.model_json_schema()}


@router.get("/events/keys")
def event_keys() -> list[dict[str, str]]:
    return [signing.public_key()]


async def _create(
    tx: Tx, principal: CurrentPrincipal, project_id: uuid.UUID | None, body: SubscriptionIn
) -> CreatedOut:
    new = events.NewSubscription(body.name, body.url, body.event_types, project_id)
    row, secret = await events.subscribe(tx, new, principal.superadmin)
    return CreatedOut(subscription=SubscriptionOut.of(row), secret=secret)


@router.post("/projects/{project_id}/event-subscriptions", status_code=201)
async def create_project_subscription(
    project_id: uuid.UUID, body: SubscriptionIn, tx: Tx, principal: CurrentPrincipal
) -> CreatedOut:
    return await _create(tx, principal, project_id, body)


@router.post("/admin/event-subscriptions", status_code=201)
async def create_system_subscription(
    body: SubscriptionIn, tx: Tx, principal: CurrentPrincipal
) -> CreatedOut:
    return await _create(tx, principal, None, body)


@router.get("/projects/{project_id}/event-subscriptions")
async def project_subscriptions(
    project_id: uuid.UUID, tx: Tx, principal: CurrentPrincipal
) -> list[SubscriptionOut]:
    rows = await events.subscriptions(tx, project_id, principal.superadmin)
    return [SubscriptionOut.of(r) for r in rows]


@router.get("/admin/event-subscriptions")
async def system_subscriptions(tx: Tx, principal: CurrentPrincipal) -> list[SubscriptionOut]:
    return [
        SubscriptionOut.of(r) for r in await events.subscriptions(tx, None, principal.superadmin)
    ]


@router.patch("/event-subscriptions/{subscription_id}", status_code=204)
async def set_enabled(
    subscription_id: uuid.UUID, body: EnabledIn, tx: Tx, principal: CurrentPrincipal
) -> None:
    await events.set_enabled(tx, subscription_id, body.enabled, principal.superadmin)


@router.delete("/event-subscriptions/{subscription_id}", status_code=204)
async def remove_subscription(
    subscription_id: uuid.UUID, tx: Tx, principal: CurrentPrincipal
) -> None:
    await events.unsubscribe(tx, subscription_id, principal.superadmin)


@router.post("/event-subscriptions/{subscription_id}/test", status_code=202)
async def test_subscription(subscription_id: uuid.UUID, tx: Tx) -> dict[str, str]:
    return {"event_id": str(await events.ping(tx, subscription_id))}


@router.get("/event-subscriptions/{subscription_id}/deliveries")
async def subscription_deliveries(subscription_id: uuid.UUID, tx: Tx) -> list[DeliveryOut]:
    rows = await events.deliveries(tx, subscription_id=subscription_id)
    return [DeliveryOut.of(d) for d in rows]


@router.post("/event-deliveries/{delivery_id}/replay", status_code=202)
async def replay_delivery(delivery_id: uuid.UUID, tx: Tx) -> dict[str, str]:
    await events.replay(tx, delivery_id)
    return {"status": "pending"}


@router.get("/projects/{project_id}/events")
async def project_events(
    project_id: uuid.UUID,
    tx: Tx,
    type_: Annotated[str | None, Query(alias="type", max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[EventOut]:
    query = select(Event).where(Event.project_id == project_id)
    if type_:
        query = query.where(Event.type == type_)
    rows = (await tx.scalars(query.order_by(Event.created_at.desc()).limit(limit))).all()
    return [EventOut.model_validate(r, from_attributes=True) for r in rows]
