"""The recall log: one row per question asked over the API (not for eval runs), in the
asker's transaction. Rows older than the retention are purged by the worker."""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.db.session import SYSTEM, transaction
from mindgrid.platform.jobs import handlers

from ..recall.types import Ask, Recall
from . import config as eval_config
from .models import RecallEvent


async def record(
    tx: AsyncSession, via: str, ask: Ask, found: Recall, elapsed_ms: int
) -> uuid.UUID | None:
    """The logged question's id (an answer may be attached to it), or None when the log is
    switched off. The id is made here, so the insert needs no RETURNING."""
    if eval_config.get_settings().recall_log_days == 0:
        return None
    event_id = uuid.uuid7()
    tx.add(
        RecallEvent(
            id=event_id,
            project_id=ask.project_id,
            via=via,
            query=ask.query[:4000],
            chunk_ids=[h.chunk_id for h in found.hits],
            skipped=dict(found.skipped),
            elapsed_ms=elapsed_ms,
        )
    )
    await tx.flush()
    return event_id


async def purge(tx: AsyncSession) -> int:
    days = eval_config.get_settings().recall_log_days
    removed = await tx.scalar(text("select mindgrid_purge_recall_events(:days)"), {"days": days})
    return int(removed or 0)


async def _purge_task() -> None:
    async with transaction(SYSTEM) as tx:
        await purge(tx)


handlers.every("knowledge.purge_recall_log", 3600, _purge_task)
