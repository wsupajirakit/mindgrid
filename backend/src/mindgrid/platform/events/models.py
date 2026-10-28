"""Subscriptions (who wants which events), events (the outbox), deliveries (one per
receiver per event) and callbacks (one-shot receivers for one subject)."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mindgrid.db.base import Base, Keyed, Timestamped


class DeliveryStatus(enum.StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    DELIVERED = "delivered"
    DEAD = "dead"  # every retry failed (or the receiver said 410 Gone): kept for replay


def _values(members: type[DeliveryStatus]) -> list[str]:
    return [m.value for m in members]


class EventSubscription(Keyed, Timestamped, Base):
    __tablename__ = "event_subscriptions"

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")  # None = every project (superadmin)
    )
    name: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(String(2000))
    event_types: Mapped[list[str]] = mapped_column(ARRAY(Text))  # exact, "area.*" or "*"
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    secret_ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    secret_nonce: Mapped[bytes] = mapped_column(LargeBinary)
    secret_version: Mapped[int] = mapped_column(SmallInteger)
    dead_in_a_row: Mapped[int] = mapped_column(Integer, default=0)
    disabled_reason: Mapped[str] = mapped_column(String(200), default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(server_default=text("mindgrid_actor()"))


class Event(Keyed, Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_project_id_created_at", "project_id", "created_at"),)

    type: Mapped[str] = mapped_column(String(100))
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    subject: Mapped[str] = mapped_column(String(300))  # e.g. "runs/<id>"
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_by: Mapped[uuid.UUID | None] = mapped_column(server_default=text("mindgrid_actor()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EventDelivery(Keyed, Base):
    __tablename__ = "event_deliveries"
    __table_args__ = (
        Index(
            "ix_event_deliveries_due",
            "next_attempt_at",
            postgresql_where=text("status in ('pending', 'sending')"),
        ),
        Index("ix_event_deliveries_event_id", "event_id"),
        Index("ix_event_deliveries_subscription_id", "subscription_id"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("event_subscriptions.id", ondelete="CASCADE")  # None = a callback
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    url: Mapped[str] = mapped_column(String(2000))
    status: Mapped[DeliveryStatus] = mapped_column(
        Enum(DeliveryStatus, name="delivery_status", values_callable=_values),
        default=DeliveryStatus.PENDING,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker: Mapped[str] = mapped_column(String(64), default="")
    last_status_code: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str] = mapped_column(Text, default="")
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_by: Mapped[uuid.UUID | None] = mapped_column()  # callbacks: who asked
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EventCallback(Keyed, Base):
    __tablename__ = "event_callbacks"
    __table_args__ = (Index("ix_event_callbacks_subject", "subject"),)

    subject: Mapped[str] = mapped_column(String(300))
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    url: Mapped[str] = mapped_column(String(2000))
    event_types: Mapped[list[str]] = mapped_column(ARRAY(Text))  # which outcomes end it
    created_by: Mapped[uuid.UUID | None] = mapped_column(server_default=text("mindgrid_actor()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
