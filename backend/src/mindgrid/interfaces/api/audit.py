"""/v1/audit: the audit log, newest first, paged by `before` (the last id seen).
A superadmin sees everything; project owners/admins see their project; everyone sees
what they did themselves. Each event names the people it mentions (actor, a user it
was about, a key's owner) so no screen shows a bare user id."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from mindgrid.platform.audit import log as audit
from mindgrid.platform.audit.models import AuditEvent
from mindgrid.platform.identity.directory import Person, people
from mindgrid.platform.tenancy import access

from .deps import Tx

router = APIRouter(prefix="/audit", tags=["audit"])


class PersonOut(BaseModel):
    name: str
    email: str
    avatar: str


class EventOut(BaseModel):
    id: uuid.UUID
    at: datetime
    actor_user_id: uuid.UUID | None
    actor_superadmin: bool
    project_id: uuid.UUID | None
    action: str
    target_type: str
    target_id: str
    details: dict[str, Any]
    request_id: str
    actor: PersonOut | None = Field(default=None, description="Who did it (if visible).")
    people: dict[str, PersonOut] = Field(
        default_factory=dict[str, PersonOut],
        description="Every user id the event mentions (target, details), with a name.",
    )

    @classmethod
    def of(cls, e: AuditEvent, named: dict[uuid.UUID, Person]) -> EventOut:
        mentioned = {str(i): _out(named[i]) for i in _mentions(e) if i in named}
        actor = named.get(e.actor_user_id) if e.actor_user_id else None
        return cls(
            id=e.id,
            at=e.at,
            actor_user_id=e.actor_user_id,
            actor_superadmin=e.actor_superadmin,
            project_id=e.project_id,
            action=e.action,
            target_type=e.target_type,
            target_id=e.target_id,
            details=e.details,
            request_id=e.request_id,
            actor=_out(actor) if actor else None,
            people=mentioned,
        )


def _out(p: Person) -> PersonOut:
    return PersonOut(name=p.name, email=p.email, avatar=p.avatar)


def _as_id(value: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def _mentions(e: AuditEvent) -> set[uuid.UUID]:
    """User ids an event refers to besides its actor: a user target, a key's owner, the
    person a category grant is for."""
    found: set[uuid.UUID] = set()
    if e.target_type == "user" and (target := _as_id(e.target_id)):
        found.add(target)
    for key in ("owner", "user"):  # a key's owner, the person a grant is for
        if person := _as_id(e.details.get(key, "")):
            found.add(person)
    return found


@router.get("")
async def list_events(
    tx: Tx,
    project_id: uuid.UUID | None = None,
    before: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=audit.MAX_PAGE),
) -> list[EventOut]:
    if project_id is not None:
        await access.require_project_view(tx, project_id)
    found = await audit.page(tx, project_id=project_id, before=before, limit=limit)
    named = await people(tx, {e.project_id for e in found if e.project_id})
    return [EventOut.of(e, named) for e in found]
