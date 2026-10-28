"""Grounded answers. `context-pack` returns what any LLM needs to answer (the caller's own
LLM writes the answer: Claude Code, a local model); `answer` lets the server write it with
the project's answer mode; `citations/verify` checks an answer against a pack; `answers`
keeps an answer the caller wrote itself with its logged question."""

import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from mindgrid.knowledge.answer import cite, pack, records
from mindgrid.knowledge.answer import service as answer_service
from mindgrid.knowledge.recall import service as recall_service
from mindgrid.platform.apikeys.models import KeyScope
from mindgrid.providers.llm.factory import Mode

from .deps import CurrentPrincipal, Tx, key_scope
from .recall import RecallIn

router = APIRouter(tags=["knowledge"])


class PassageOut(BaseModel):
    ref: str
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    heading: str
    trust: str
    location: dict[str, Any]
    text: str
    relevance: float | None


class PackOut(BaseModel):
    version: str
    query: str
    project_id: uuid.UUID
    created_at: datetime
    rules: str
    passages: list[PassageOut]
    rendered: str = Field(description="The passages as one delimited text block.")
    skipped: dict[str, str]
    space: str
    reranker: str
    dropped: int
    recall_id: uuid.UUID | None = Field(
        None, description="The logged question; report your own answer to it (POST /answers)."
    )

    @classmethod
    def of(cls, p: pack.ContextPack) -> PackOut:
        return cls(
            version=p.version,
            query=p.query,
            project_id=p.project_id,
            created_at=p.created_at,
            rules=p.rules,
            passages=[PassageOut.model_validate(x, from_attributes=True) for x in p.passages],
            rendered=pack.render(p),
            skipped=p.skipped,
            space=p.space,
            reranker=p.reranker,
            dropped=p.dropped,
            recall_id=p.recall_id,
        )


class CheckOut(BaseModel):
    ok: bool
    cited: list[str]
    unknown: list[str]
    uncited: list[str]

    @classmethod
    def of(cls, c: cite.CitationCheck) -> CheckOut:
        return cls(ok=c.ok, cited=c.cited, unknown=c.unknown, uncited=c.uncited)


class AnswerIn(RecallIn):
    llm: Mode | None = Field(None, description="Override the project's answer mode.")
    callback_url: str | None = Field(
        None, max_length=2000, description="Also receives answer.completed (signed)."
    )


class AnswerOut(BaseModel):
    answer_id: uuid.UUID
    mode: Mode
    answer: str | None
    writer: str
    check: CheckOut | None
    pack: PackOut


class VerifyIn(BaseModel):
    answer: str = Field(max_length=100_000)
    refs: list[str] = Field(max_length=500, description="The pack's passage references.")


def _ask(project_id: uuid.UUID, body: RecallIn) -> recall_service.Ask:
    return recall_service.Ask(project_id, body.query, tuple(body.categories), body.k)


@router.post("/projects/{project_id}/context-pack", openapi_extra=key_scope(KeyScope.READ))
async def context_pack(project_id: uuid.UUID, body: RecallIn, tx: Tx) -> PackOut:
    return PackOut.of(await answer_service.context_pack(tx, _ask(project_id, body)))


@router.post("/projects/{project_id}/answer", openapi_extra=key_scope(KeyScope.RUN))
async def answer(project_id: uuid.UUID, body: AnswerIn, principal: CurrentPrincipal) -> AnswerOut:
    ask = _ask(project_id, body)
    channel = "web" if principal.session_id else "api"
    done = await answer_service.answer(
        principal.actor, ask, body.llm, body.callback_url, channel=channel
    )
    return AnswerOut(
        answer_id=done.answer_id,
        mode=done.mode,
        answer=done.text,
        writer=done.writer,
        check=CheckOut.of(done.check) if done.check else None,
        pack=PackOut.of(done.pack),
    )


@router.post("/citations/verify", openapi_extra=key_scope(KeyScope.READ))
def verify_citations(body: VerifyIn, principal: CurrentPrincipal) -> CheckOut:
    del principal  # signed-in callers only; the check itself reads no data
    return CheckOut.of(cite.verify(body.answer, body.refs))


class AnswerReport(BaseModel):
    recall_id: uuid.UUID = Field(description="From the Context Pack you answered from.")
    answer: str = Field(min_length=1, max_length=records.MAX_TEXT)
    refs: list[str] = Field(max_length=500, description="The pack's passage references.")
    writer: str = Field("", max_length=100, description="Who wrote it, e.g. a model name.")
    channel: Literal["api", "mcp", "cli"] = "api"


class ReportedOut(BaseModel):
    answer_id: uuid.UUID
    check: CheckOut


@router.post("/answers", status_code=201, openapi_extra=key_scope(KeyScope.READ))
async def report_answer(body: AnswerReport, tx: Tx) -> ReportedOut:
    """Keep the answer you wrote yourself with your own logged question, checked against the
    pack's references (it then shows in the results history)."""
    writer = body.writer.strip() or body.channel
    written = records.Written(body.channel, writer, body.answer, None)
    answer_id, check = await records.report(tx, body.recall_id, written, body.refs)
    return ReportedOut(answer_id=answer_id, check=CheckOut.of(check))
