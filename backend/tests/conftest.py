"""Shared fixtures. Tests read the process environment only, reset between cases.

Database tests (marker `db`) run against MINDGRID_TEST_DATABASE_URL, migrated once per
run with MINDGRID_TEST_MIGRATION_DATABASE_URL; every table is emptied before each test,
except reference tables (comment "reference data: ...", seeded by migrations).
Without the URL they skip, unless MINDGRID_REQUIRE_DB=1 (the commit gate) makes it fail.
"""

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from mindgrid.core import config
from mindgrid.db import engine as db_engine

BACKEND = Path(__file__).resolve().parents[1]
os.environ.setdefault("MINDGRID_SECRET_KEY", "test-only-server-secret-" + "x" * 32)
# No model downloads in tests: reranking is off unless a test swaps in a fake reranker.
os.environ.setdefault("MINDGRID_RERANK_PROVIDER", "none")
_TEST_URL = "MINDGRID_TEST_DATABASE_URL"
_TEST_OWNER_URL = "MINDGRID_TEST_MIGRATION_DATABASE_URL"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if os.environ.get(_TEST_URL):
        return
    if os.environ.get("MINDGRID_REQUIRE_DB") == "1":
        raise pytest.UsageError(f"{_TEST_URL} is not set (source tools/dev_env.sh)")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(pytest.mark.skip(reason=f"set {_TEST_URL}"))


@pytest.fixture(scope="session")
def _migrated() -> None:
    env = {**os.environ, "MINDGRID_MIGRATION_DATABASE_URL": os.environ[_TEST_OWNER_URL]}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env, check=True
    )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def _empty_tables() -> None:
    owner = create_async_engine(os.environ[_TEST_OWNER_URL])
    async with owner.begin() as conn:
        tables = (
            await conn.execute(
                text(
                    "select string_agg(quote_ident(tablename), ', ') from pg_tables"
                    " where schemaname = 'public' and tablename <> 'alembic_version'"
                    " and coalesce(obj_description(format('%I', tablename)::regclass,"
                    " 'pg_class'), '') not like 'reference data%'"
                )
            )
        ).scalar()
        if tables:
            await conn.execute(text(f"truncate {tables} cascade"))
    await owner.dispose()


@pytest.fixture
async def db(_migrated: None, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """A clean test database for async tests of app code."""
    await _empty_tables()
    monkeypatch.setenv("MINDGRID_DATABASE_URL", os.environ[_TEST_URL])
    config.reset()
    yield
    await db_engine.dispose()


@pytest.fixture
def api_db(_migrated: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """A clean test database for API tests (the app disposes its engine on shutdown)."""
    asyncio.run(_empty_tables())
    monkeypatch.setenv("MINDGRID_DATABASE_URL", os.environ[_TEST_URL])
    config.reset()


@pytest.fixture(autouse=True)
def _fresh_settings() -> Iterator[None]:
    config.reset()
    yield
    config.reset()


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Set variables for one test (None unsets one); cached settings re-read them."""

    def apply(**values: str | None) -> None:
        for name, value in values.items():
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, value)
        config.reset()

    return apply


@pytest.fixture
def owner_sql(_migrated: None) -> Callable[[str], Awaitable[None]]:
    """Run one statement as the owner role, past row-level security and grants (tests use
    it to move clocks, e.g. expire a lease)."""

    async def run(statement: str) -> None:
        owner = create_async_engine(os.environ[_TEST_OWNER_URL])
        async with owner.begin() as conn:
            await conn.execute(text(statement))
        await owner.dispose()

    return run
