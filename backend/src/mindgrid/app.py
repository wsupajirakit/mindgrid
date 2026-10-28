"""Application factory: `uvicorn --factory mindgrid.app:create_app`.

Every Settings class is validated once the routers are imported, so a malformed value
stops the boot instead of failing a request later.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from mindgrid.core import brand, config, runtime
from mindgrid.core import logging as app_logging
from mindgrid.core.errors import install_error_handlers
from mindgrid.core.request_id import RequestId
from mindgrid.db import engine as db_engine
from mindgrid.interfaces import web
from mindgrid.interfaces.api import (
    admin_keys,
    admin_users,
    answer,
    audit,
    auth,
    categories,
    data,
    documents,
    evals,
    events,
    groups,
    insights,
    keys,
    meta,
    playbooks,
    project_copy,
    projects,
    recall,
    runs,
    secrets,
    settings,
    synapse,
)
from mindgrid.interfaces.body_limit import BodySizeLimit
from mindgrid.knowledge.recall import warmup
from mindgrid.platform.security import config as security_config

API_PREFIX = "/v1"


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncGenerator[None]:
    warming = asyncio.create_task(warmup.warm())  # local models load while serving
    yield
    warming.cancel()
    await db_engine.dispose()  # close pooled connections on shutdown


def create_app() -> FastAPI:
    app_logging.configure()
    docs_on = runtime.get_settings().docs
    app = FastAPI(
        lifespan=_lifespan,
        title=brand.get_settings().name,
        docs_url="/docs" if docs_on else None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json" if docs_on else None,
    )
    install_error_handlers(app)
    app.include_router(meta.router, prefix=API_PREFIX)
    routers = (
        auth,
        keys,
        projects,
        categories,
        documents,
        recall,
        answer,
        evals,
        playbooks,
        runs,
        data,
        events,
        synapse,
        admin_users,
        admin_keys,
        audit,
        settings,
        secrets,
        insights,
        groups,
        project_copy,
    )
    for module in routers:
        app.include_router(module.router, prefix=API_PREFIX)
    web.mount(app, API_PREFIX)  # last: its catch-all must not shadow API routes
    app.add_middleware(RequestId)
    app.add_middleware(BodySizeLimit)
    app.add_middleware(web.SecurityHeaders)
    config.validate_all()
    security_config.secret_bytes()  # no server secret, no start
    return app
