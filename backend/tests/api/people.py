"""Shared by the HTTP tests: the people they act as, and signing in as one of them."""

import asyncio

from fastapi.testclient import TestClient

from mindgrid.db import engine as db_engine
from mindgrid.db.session import Actor, transaction
from mindgrid.interfaces.api.deps import CSRF_COOKIE
from mindgrid.platform.identity import users
from mindgrid.platform.identity.models import SystemRole

PASSWORD = "Correct horse battery 9"
PEOPLE = {"root": SystemRole.SUPERADMIN, "alice": SystemRole.USER, "bob": SystemRole.USER}


def seed_people() -> None:
    async def run() -> None:
        async with transaction(Actor(None, superadmin=True)) as tx:
            for name, role in PEOPLE.items():
                await users.create_user(
                    tx,
                    email=f"{name}@example.com",
                    display_name=name,
                    password=PASSWORD,
                    system_role=role,
                )
        await db_engine.dispose()

    asyncio.run(run())


def sign_in(client: TestClient, name: str) -> dict[str, str]:
    """Sign in as `name` (replacing the cookies); returns the CSRF header for writes."""
    client.cookies.clear()
    r = client.post("/v1/auth/sign-in", json={"email": f"{name}@example.com", "password": PASSWORD})
    assert r.status_code == 200
    return {"X-CSRF-Token": client.cookies.get(CSRF_COOKIE) or ""}
