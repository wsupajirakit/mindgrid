"""Sources (superadmin), checks (worker job, as the source's creator), proposals and
their review: accepting a knowledge item writes a document version into the source's
target category; accepting a code or measurement item records it as a task."""

import functools
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from pathlib import PurePosixPath
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.db.session import SYSTEM, Actor, transaction
from mindgrid.knowledge.library import service as library
from mindgrid.knowledge.library.models import Document, Trust
from mindgrid.platform.events import service as events
from mindgrid.platform.jobs import handlers, queue
from mindgrid.platform.tenancy import access

from . import events as synapse_events
from . import git, propose
from .models import SynapseProposal, SynapseSource
from .understand import Mapping

KIND = "synapse.check"
TEXT_SUFFIXES = {".md", ".txt", ".csv", ".markdown"}


@dataclass(frozen=True, slots=True)
class NewSource:
    name: str
    path: str
    mapping: Mapping
    project_id: uuid.UUID
    category_id: uuid.UUID
    every_minutes: int | None = None


@functools.cache
def templates() -> list[dict[str, Any]]:
    folder = files("mindgrid.synapse.templates")
    found = [
        json.loads(f.read_text(encoding="utf-8"))
        for f in sorted(folder.iterdir(), key=lambda f: f.name)
        if f.name.endswith(".json")
    ]
    for item in found:
        Mapping.model_validate(item["mapping"])  # a broken template fails at start-up
    return found


def _superadmin(superadmin: bool) -> None:
    if not superadmin:
        raise ApiError(403, "auth.superadmin_only", "superadmin only")


async def add_source(tx: AsyncSession, new: NewSource, superadmin: bool) -> SynapseSource:
    _superadmin(superadmin)
    try:
        git.check_path(new.path)
    except git.GitError as err:
        raise ApiError(400, "synapse.bad_source", str(err)) from err
    if await access.project_of_category(tx, new.category_id) != new.project_id:
        raise ApiError(400, "synapse.bad_target", "the category is not in that project")
    row = SynapseSource(
        name=new.name,
        path=new.path,
        mapping=new.mapping.model_dump(),
        project_id=new.project_id,
        category_id=new.category_id,
        every_minutes=new.every_minutes,
        # the first scheduled check waits one interval: a manual check comes first
        next_check_at=(
            datetime.now(UTC) + timedelta(minutes=new.every_minutes) if new.every_minutes else None
        ),
    )
    tx.add(row)
    await tx.flush()
    await tx.refresh(row)
    return row


async def sources(tx: AsyncSession, superadmin: bool) -> list[SynapseSource]:
    _superadmin(superadmin)
    return list((await tx.scalars(select(SynapseSource).order_by(SynapseSource.name))).all())


async def request_check(
    tx: AsyncSession, source_id: uuid.UUID, import_all: bool, superadmin: bool
) -> None:
    _superadmin(superadmin)
    row = await tx.get(SynapseSource, source_id)
    if row is None:
        raise ApiError(404, "synapse.not_found", "source not found")
    payload = {"source_id": str(row.id), "import_all": import_all, "subject": f"synapse/{row.id}"}
    await queue.enqueue(tx, queue.NewJob(KIND, payload, row.project_id))


async def _record(tx: AsyncSession, row: SynapseSource, head: str, built: propose.Built) -> None:
    proposal = SynapseProposal(
        source_id=row.id,
        project_id=row.project_id,
        from_commit=row.last_commit,
        to_commit=head,
        items=[i.as_json() for i in built.items],
        redactions=built.redactions,
    )
    tx.add(proposal)
    await tx.flush()
    data = synapse_events.ProposalCreated(
        proposal_id=str(proposal.id),
        source=row.name,
        from_commit=row.last_commit,
        to_commit=head,
        items=len(built.items),
        links=events.link(
            f"/v1/synapse/proposals/{proposal.id}", f"/admin/synapse?proposal={proposal.id}"
        ),
    )
    await events.emit(tx, data, project_id=row.project_id, subject=f"synapse/{row.id}")


async def _check(actor: Actor, payload: dict[str, Any]) -> None:
    source_id = uuid.UUID(str(payload.get("source_id", "")))
    async with transaction(actor) as tx:
        row = await tx.get(SynapseSource, source_id)
        if row is None:
            raise handlers.PermanentJobError("the source is gone")
        repo, mapping, last = (
            git.check_path(row.path),
            Mapping.model_validate(row.mapping),
            row.last_commit,
        )
    head = git.head(repo)
    built = None
    if payload.get("import_all"):  # everything wanted at head, whatever was learned before
        built = propose.build(repo, None, head, mapping)
    elif last and head != last:
        built = propose.build(repo, last, head, mapping)
    async with transaction(actor) as tx:
        row = await tx.get(SynapseSource, source_id)
        if row is None:
            return
        if built is not None and built.items:
            await _record(tx, row, head, built)
        row.last_commit, row.last_checked_at, row.last_error = head, datetime.now(UTC), ""
        if row.every_minutes:
            row.next_check_at = datetime.now(UTC) + timedelta(minutes=row.every_minutes)


async def proposals(tx: AsyncSession, status: str | None = None) -> list[SynapseProposal]:
    query = select(SynapseProposal).order_by(SynapseProposal.created_at.desc()).limit(100)
    if status:
        query = query.where(SynapseProposal.status == status)
    return list((await tx.scalars(query)).all())


async def get_proposal(tx: AsyncSession, proposal_id: uuid.UUID) -> SynapseProposal:
    row = await tx.get(SynapseProposal, proposal_id)
    if row is None:
        raise ApiError(404, "synapse.not_found", "proposal not found")
    return row


def _filename(path: str) -> str:
    return path if PurePosixPath(path).suffix.lower() in TEXT_SUFFIXES else path + ".txt"


async def _apply_knowledge(tx: AsyncSession, source: SynapseSource, item: dict[str, Any]) -> None:
    found = await tx.scalar(
        select(Document).where(
            Document.category_id == source.category_id,
            Document.title == item["path"][:300],
            Document.source == "synapse",
        )
    )
    if item["kind"] == "knowledge_remove":
        if found is not None:
            await library.remove_document(tx, found.id)
        return
    upload = library.Upload(
        filename=_filename(item["path"]),
        data=item["detail"]["text"].encode(),
        title=item["path"][:300],
        trust=Trust.CLAIMED,
    )
    if found is None:
        doc = await library.add_document(tx, source.category_id, upload)
        doc.source = "synapse"
    else:
        await library.add_version(tx, found, upload)


async def decide(
    tx: AsyncSession, proposal_id: uuid.UUID, index: int, accept: bool
) -> dict[str, Any]:
    proposal = await get_proposal(tx, proposal_id)
    await access.require_project_manage(tx, proposal.project_id)
    if not 0 <= index < len(proposal.items) or proposal.items[index]["decision"] != "pending":
        raise ApiError(409, "synapse.item_decided", "no pending item at that position")
    items = [dict(i) for i in proposal.items]
    item = items[index]
    if accept and item["kind"] in ("knowledge_update", "knowledge_remove"):
        source = await tx.get(SynapseSource, proposal.source_id)
        if source is None:
            raise ApiError(404, "synapse.not_found", "source not found")
        await _apply_knowledge(tx, source, item)
    item["decision"] = "accepted" if accept else "rejected"
    proposal.items = items
    if all(i["decision"] != "pending" for i in items):
        proposal.status, proposal.reviewed_at = "reviewed", datetime.now(UTC)
    return item


def tasks_markdown(proposal: SynapseProposal) -> str:
    """Accepted code and measurement items as a checklist (for a ticket or a pull request)."""
    lines = [
        f"# Source changes {proposal.from_commit[:10] or 'start'}..{proposal.to_commit[:10]}",
        "",
    ]
    for item in proposal.items:
        if item["decision"] != "accepted" or item["kind"] not in ("code_task", "measure"):
            continue
        fns = ", ".join(item["detail"].get("functions") or [])
        what = "Re-measure on the engine's data" if item["kind"] == "measure" else "Port the change"
        lines.append(
            f"- [ ] {what}: `{item['path']}` — {item['summary']}" + (f" ({fns})" if fns else "")
        )
    return "\n".join(lines) + "\n"


async def _enqueue_due() -> None:
    async with transaction(SYSTEM) as tx:
        await tx.execute(text("select mindgrid_enqueue_due_synapse()"))


handlers.register(KIND, _check)
handlers.every("synapse.schedule", 60, _enqueue_due)
