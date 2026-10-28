"""Context Pack and answers. Recall runs in its own transaction, which ends before any
model is called, so a slow model never holds a database connection."""

import dataclasses
import time
import uuid
from dataclasses import dataclass, field
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.core.settings_registry import Scope
from mindgrid.db.session import Actor, transaction
from mindgrid.platform.events import service as events
from mindgrid.platform.settings import service as settings_service
from mindgrid.providers.llm import factory
from mindgrid.providers.llm.base import Prompt, Writer, WriterError

from .. import assist
from ..evals import log as recall_log
from ..recall import service as recall_service
from . import cite, pack, records
from . import events as answer_events
from .settings import ANSWER_LLM

NOT_FOUND = "The knowledge base has nothing on this question yet."


@dataclass(frozen=True, slots=True)
class Answered:
    pack: pack.ContextPack
    mode: factory.Mode
    text: str | None  # None in mode "none": the caller writes the answer
    writer: str = ""
    check: cite.CitationCheck | None = None
    answer_id: uuid.UUID = field(default_factory=uuid.uuid7)


async def context_pack(
    tx: AsyncSession, ask: recall_service.Ask, via: str = "context-pack"
) -> pack.ContextPack:
    """Recall + pack, logged in the recall log under `via`."""
    started = time.perf_counter()
    found = await recall_service.recall(tx, ask)
    elapsed = round((time.perf_counter() - started) * 1000)
    recall_id = await recall_log.record(tx, via, ask, found, elapsed)
    return dataclasses.replace(pack.build(ask.project_id, ask.query, found), recall_id=recall_id)


async def _mode(
    tx: AsyncSession, project_id: uuid.UUID, chosen: factory.Mode | None
) -> factory.Mode:
    if chosen is not None:
        return chosen
    chain: list[tuple[Scope, uuid.UUID | None]] = [
        (Scope.PROJECT, project_id),
        (Scope.SYSTEM, None),
    ]
    resolved = await settings_service.resolve(tx, ANSWER_LLM.key, chain)
    return cast(factory.Mode, resolved.value)


async def answer_mode(tx: AsyncSession, project_id: uuid.UUID) -> factory.Mode:
    """The project's answer.llm setting."""
    return await _mode(tx, project_id, None)


async def writer_or_none(
    tx: AsyncSession, project_id: uuid.UUID, mode: factory.Mode
) -> Writer | None:
    """The writer for a mode, or None when the mode is none or cannot run."""
    try:
        return await assist.writer_for(tx, project_id, mode)
    except factory.WriterUnavailableError:
        return None


async def _writer(tx: AsyncSession, project_id: uuid.UUID, mode: factory.Mode) -> Writer | None:
    try:
        return await assist.writer_for(tx, project_id, mode)
    except factory.WriterUnavailableError as err:
        raise ApiError(409, "answer.llm_unavailable", str(err), params={"mode": mode}) from err


async def write_pack(
    found: pack.ContextPack, mode: factory.Mode, writer: Writer | None
) -> Answered:
    """The answer to a pack (outside any transaction: the model call may be slow)."""
    if writer is None:
        return Answered(found, mode, None)
    if not found.passages:
        return Answered(found, mode, NOT_FOUND, writer.name, cite.CitationCheck())
    found = pack.fit(found, writer.max_prompt_chars)
    try:
        text = await writer.write(Prompt(pack.RULES, pack.user_prompt(found)))
    except WriterError as err:
        raise ApiError(502, "answer.llm_failed", str(err), params={"mode": mode}) from err
    return Answered(found, mode, text, writer.name, cite.verify(text, found.refs))


async def _announce(actor: Actor, done: Answered, callback_url: str | None) -> None:
    project_id = done.pack.project_id
    subject = f"answers/{done.answer_id}"
    data = answer_events.AnswerCompleted(
        answer_id=str(done.answer_id),
        mode=done.mode,
        writer=done.writer,
        passages=len(done.pack.passages),
        citations_ok=done.check.ok if done.check else None,
        links=events.link(f"/v1/projects/{project_id}/answer", f"/projects/{project_id}?tab=ask"),
    )
    async with transaction(actor) as tx:
        if callback_url:
            await events.register_callback(
                tx, subject, project_id, callback_url, [answer_events.ANSWER_COMPLETED.name]
            )
        await events.emit(tx, data, project_id=project_id, subject=subject)


async def _keep(actor: Actor, done: Answered, channel: records.Channel) -> None:
    """A written answer is kept with its logged question (nothing to keep in mode none)."""
    if done.text is None or done.pack.recall_id is None or not done.pack.passages:
        return
    async with transaction(actor) as tx:
        written = records.Written(channel, done.writer, done.text, done.check)
        await records.store(
            tx, done.pack.recall_id, done.pack.project_id, written, answer_id=done.answer_id
        )


async def answer(
    actor: Actor,
    ask: recall_service.Ask,
    chosen: factory.Mode | None,
    callback_url: str | None = None,
    channel: records.Channel = "api",
) -> Answered:
    async with transaction(actor) as tx:
        found = await context_pack(tx, ask, via="answer")
        mode = await _mode(tx, ask.project_id, chosen)
        writer = await _writer(tx, ask.project_id, mode)
    done = await write_pack(found, mode, writer)
    await _keep(actor, done, channel)
    await _announce(actor, done, callback_url)
    return done
