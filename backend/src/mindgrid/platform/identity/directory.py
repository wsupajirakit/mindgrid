"""Names for user ids, for every screen that shows who did something (history, results,
key owners). Row-level security decides who is visible: oneself, everyone for a
superadmin, and the members of the given projects."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User


@dataclass(frozen=True, slots=True)
class Person:
    name: str
    email: str
    avatar: str


async def people(tx: AsyncSession, project_ids: set[uuid.UUID]) -> dict[uuid.UUID, Person]:
    found = {
        u.id: Person(u.display_name, u.email, u.avatar) for u in await tx.scalars(select(User))
    }
    for pid in project_ids:
        rows = await tx.execute(
            text("select * from mindgrid_project_member_profiles(:p)"), {"p": pid}
        )
        for r in rows:
            found.setdefault(r.user_id, Person(r.display_name, r.email, r.avatar))
    return found
