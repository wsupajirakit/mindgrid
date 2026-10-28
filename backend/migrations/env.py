"""Alembic environment (async). Runs as the owner role; every model module is imported so
`alembic check` compares the full schema."""

import asyncio
import importlib
import pkgutil

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

import mindgrid
from mindgrid.db import config as db_config
from mindgrid.db.base import Base

for _mod in pkgutil.walk_packages(mindgrid.__path__, "mindgrid."):
    if _mod.name.endswith(".models"):
        importlib.import_module(_mod.name)

target_metadata = Base.metadata
# Built at run time, one per embedding space (mindgrid_ensure_embedding_space).
RUNTIME_INDEX_PREFIX = "ix_chunk_embeddings_hnsw_"


def _include(obj, name, type_, reflected, compare_to) -> bool:
    return not (type_ == "index" and reflected and (name or "").startswith(RUNTIME_INDEX_PREFIX))


def _run(connection) -> None:
    context.configure(
        connection=connection, target_metadata=target_metadata, include_object=_include
    )
    with context.begin_transaction():
        context.run_migrations()


async def _main() -> None:
    engine = create_async_engine(db_config.migration_url())
    async with engine.connect() as conn:
        await conn.run_sync(_run)
    await engine.dispose()


asyncio.run(_main())
