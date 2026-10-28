"""Public metadata: liveness, readiness (the database answers) and the displayed brand
(needed before sign-in)."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from mindgrid.core import brand
from mindgrid.db.session import SYSTEM, transaction

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", response_model=None)
async def ready() -> dict[str, str] | JSONResponse:
    try:
        async with transaction(SYSTEM) as tx:
            await tx.execute(text("select 1"))
    except Exception:  # any database failure means not ready; details stay in the logs
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return {"status": "ready"}


@router.get("/meta/brand")
def meta_brand() -> brand.Brand:
    return brand.current()
