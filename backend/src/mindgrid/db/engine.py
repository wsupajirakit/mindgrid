"""One async engine per process, created on first use."""

import functools

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mindgrid.db import config as db_config


@functools.cache
def get_engine() -> AsyncEngine:
    cfg = db_config.get_settings()
    return create_async_engine(
        db_config.app_url(),
        pool_size=cfg.pool_size,
        pool_pre_ping=True,
        connect_args={"server_settings": {"statement_timeout": str(cfg.statement_timeout_ms)}},
    )


async def dispose() -> None:
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
        get_engine.cache_clear()
