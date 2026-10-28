"""Answers kept with their question in the recall log: written by the server, or reported
back by a client that wrote it itself (an MCP host, the CLI). Every stored answer carries
its citation check against the references the question's pack had."""

import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError

from ..evals.models import AnswerRecord, RecallEvent
from . import cite

Channel = Literal["web", "api", "mcp", "cli"]
MAX_TEXT = 100_000


@dataclass(frozen=True, slots=True)
class Written:
    channel: Channel
    writer: str  # provider:model, or mcp:<client name>
    text: str
    check: cite.CitationCheck | None


async def store(
    tx: AsyncSession,
    recall_id: uuid.UUID,
    project_id: uuid.UUID,
    written: Written,
    answer_id: uuid.UUID | None = None,
) -> uuid.UUID:
    answer_id = answer_id or uuid.uuid7()  # made here: the insert needs no RETURNING
    check = written.check
    tx.add(
        AnswerRecord(
            id=answer_id,
            recall_event_id=recall_id,
            project_id=project_id,
            channel=written.channel,
            writer=written.writer[:200],
            text=written.text[:MAX_TEXT],
            check_ok=check.ok if check else None,
            cited=list(check.cited) if check else [],
            unknown=list(check.unknown) if check else [],
            uncited=len(check.uncited) if check else 0,
        )
    )
    await tx.flush()
    return answer_id


async def report(
    tx: AsyncSession, recall_id: uuid.UUID, written: Written, refs: list[str]
) -> tuple[uuid.UUID, cite.CitationCheck]:
    """A client's own answer to its own logged question: checked, then stored."""
    event = await tx.scalar(select(RecallEvent).where(RecallEvent.id == recall_id))
    if event is None:  # unknown, purged, or asked by someone else (row-level security)
        raise ApiError(404, "answer.question_not_found", "no such question in your log")
    check = cite.verify(written.text, refs)
    checked = Written(written.channel, written.writer, written.text, check)
    return await store(tx, event.id, event.project_id, checked), check
