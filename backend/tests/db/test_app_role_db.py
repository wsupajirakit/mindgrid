"""The migration step makes the app role itself: created when missing, password and limits
aligned when it exists, never superuser or BYPASSRLS."""

import os
import uuid
from collections.abc import Callable

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from mindgrid.db import app_role

pytestmark = [pytest.mark.anyio, pytest.mark.db]


async def _can_log_in(url: str) -> bool:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
        return True
    except Exception:  # wrong password or no such role
        return False
    finally:
        await engine.dispose()


async def _flags(owner: str, role: str) -> tuple[bool, bool, bool]:
    engine = create_async_engine(owner)
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("select rolsuper, rolbypassrls, rolcanlogin from pg_roles where rolname = :r"),
                {"r": role},
            )
        ).one()
    await engine.dispose()
    return bool(row[0]), bool(row[1]), bool(row[2])


@pytest.mark.usefixtures("_migrated")
async def test_role_is_created_then_kept_in_line(env: Callable[..., None]) -> None:
    owner = os.environ["MINDGRID_TEST_MIGRATION_DATABASE_URL"]
    base = make_url(os.environ["MINDGRID_TEST_DATABASE_URL"])
    role = f"mg_role_{uuid.uuid4().hex[:10]}"
    first, second = "pw-" + uuid.uuid4().hex, "pw:'quote\"@/" + uuid.uuid4().hex

    def url(password: str) -> str:
        return base.set(username=role, password=password).render_as_string(hide_password=False)

    env(MINDGRID_DB_APP_ROLE=role, MINDGRID_MIGRATION_DATABASE_URL=owner)
    try:
        env(MINDGRID_DATABASE_URL=url(first))
        assert await app_role.ensure() == "created"
        assert await _can_log_in(url(first))
        assert await _flags(owner, role) == (False, False, True)

        env(MINDGRID_DATABASE_URL=url(second))  # a changed password (with quote characters)
        assert await app_role.ensure() == "updated"
        assert await _can_log_in(url(second))
        assert not await _can_log_in(url(first))
    finally:
        engine = create_async_engine(owner)
        async with engine.begin() as conn:
            await conn.exec_driver_sql(f'drop owned by "{role}"')
            await conn.exec_driver_sql(f'drop role if exists "{role}"')
        await engine.dispose()


async def test_url_must_log_in_as_the_app_role(env: Callable[..., None]) -> None:
    env(
        MINDGRID_DB_APP_ROLE="mindgrid_app",
        MINDGRID_DATABASE_URL="postgresql+asyncpg://someone_else:pw@localhost/x",
    )
    with pytest.raises(RuntimeError, match="must log in as mindgrid_app"):
        await app_role.ensure()
