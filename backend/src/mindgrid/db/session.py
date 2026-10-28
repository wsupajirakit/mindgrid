"""Transactions bound to the acting principal. Row-level security policies read
`mindgrid.user_id`, `mindgrid.superadmin` and `mindgrid.projects`, set with SET LOCAL so
they end with the transaction and never leak to the next user of a pooled connection."""

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mindgrid.db.engine import get_engine


@dataclass(frozen=True, slots=True)
class Actor:
    """Who the database acts for. `None` user = a system task (no row is visible to it
    unless a policy grants system access explicitly)."""

    user_id: uuid.UUID | None
    superadmin: bool = False
    # An API key limited to some projects: only these count (empty = no limit).
    projects: tuple[uuid.UUID, ...] = ()


SYSTEM = Actor(user_id=None)


def _factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


@asynccontextmanager
async def transaction(actor: Actor) -> AsyncGenerator[AsyncSession]:
    async with _factory()() as session, session.begin():
        await session.execute(
            text(
                "select set_config('mindgrid.user_id', :uid, true),"
                " set_config('mindgrid.superadmin', :sa, true),"
                " set_config('mindgrid.projects', :projects, true)"
            ),
            {
                "uid": str(actor.user_id or ""),
                "sa": "on" if actor.superadmin else "off",
                "projects": ",".join(str(p) for p in actor.projects),
            },
        )
        yield session
