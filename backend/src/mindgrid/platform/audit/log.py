"""Write and read audit events."""

import uuid
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import CODE_PATTERN

from .models import AuditEvent

MAX_PAGE = 200


@dataclass(frozen=True, slots=True)
class Target:
    """What an event is about, e.g. Target("project", project.id)."""

    kind: str
    id: object


async def record(
    tx: AsyncSession,
    action: str,
    *,
    project_id: uuid.UUID | None = None,
    target: Target | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    if not CODE_PATTERN.fullmatch(action):
        raise ValueError(f"audit action must be a dotted code, got {action!r}")
    request_id = str(structlog.contextvars.get_contextvars().get("request_id", ""))
    # No RETURNING (see the model): the writer need not be able to read the event back.
    await tx.execute(
        insert(AuditEvent).values(
            project_id=project_id,
            action=action,
            target_type=target.kind if target else "",
            target_id=str(target.id) if target else "",
            details=details or {},
            request_id=request_id,
        )
    )


async def page(
    tx: AsyncSession, *, project_id: uuid.UUID | None, before: uuid.UUID | None, limit: int
) -> list[AuditEvent]:
    """Newest first; `before` is the id of the last event of the previous page (ids are
    UUIDv7, so they sort by time). Row-level security decides what is visible."""
    query = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(min(max(limit, 1), MAX_PAGE))
    if project_id is not None:
        query = query.where(AuditEvent.project_id == project_id)
    if before is not None:
        query = query.where(AuditEvent.id < before)
    return list((await tx.scalars(query)).all())
