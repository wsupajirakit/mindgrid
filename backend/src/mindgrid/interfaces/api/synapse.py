"""/v1/synapse: learning from source repositories. Sources are superadmin-only; proposals
are reviewed item by item by a superadmin or a manager of the target project."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from mindgrid.synapse import service as synapse
from mindgrid.synapse.models import SynapseProposal, SynapseSource
from mindgrid.synapse.understand import Mapping

from .deps import CurrentPrincipal, Tx

router = APIRouter(tags=["synapse"])


class SourceIn(BaseModel):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,99}$")
    path: str = Field(min_length=1, max_length=1000)
    mapping: Mapping
    project_id: uuid.UUID
    category_id: uuid.UUID
    every_minutes: int | None = Field(None, ge=5, le=7 * 24 * 60)


class SourceOut(BaseModel):
    id: uuid.UUID
    name: str
    project_id: uuid.UUID
    category_id: uuid.UUID
    enabled: bool
    every_minutes: int | None
    last_commit: str
    last_checked_at: datetime | None
    last_error: str

    @classmethod
    def of(cls, s: SynapseSource) -> SourceOut:
        return cls.model_validate(s, from_attributes=True)


class ProposalOut(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    project_id: uuid.UUID
    from_commit: str
    to_commit: str
    status: str
    items: list[dict[str, Any]]
    redactions: int
    created_at: datetime

    @classmethod
    def of(cls, p: SynapseProposal) -> ProposalOut:
        return cls.model_validate(p, from_attributes=True)


class CheckIn(BaseModel):
    import_all: bool = Field(False, description="First check: propose every wanted file now.")


class DecisionIn(BaseModel):
    accept: bool


@router.get("/synapse/templates")
def templates() -> list[dict[str, Any]]:
    return synapse.templates()


@router.post("/admin/synapse/sources", status_code=201)
async def add_source(body: SourceIn, tx: Tx, principal: CurrentPrincipal) -> SourceOut:
    new = synapse.NewSource(
        body.name, body.path, body.mapping, body.project_id, body.category_id, body.every_minutes
    )
    return SourceOut.of(await synapse.add_source(tx, new, principal.superadmin))


@router.get("/admin/synapse/sources")
async def list_sources(tx: Tx, principal: CurrentPrincipal) -> list[SourceOut]:
    return [SourceOut.of(s) for s in await synapse.sources(tx, principal.superadmin)]


@router.post("/admin/synapse/sources/{source_id}/check", status_code=202)
async def check_source(
    source_id: uuid.UUID, body: CheckIn, tx: Tx, principal: CurrentPrincipal
) -> dict[str, str]:
    await synapse.request_check(tx, source_id, body.import_all, principal.superadmin)
    return {"status": "queued"}


@router.get("/synapse/proposals")
async def list_proposals(
    tx: Tx, status: Annotated[str | None, Query(pattern=r"^(pending|reviewed)$")] = None
) -> list[ProposalOut]:
    return [ProposalOut.of(p) for p in await synapse.proposals(tx, status)]


@router.get("/synapse/proposals/{proposal_id}")
async def get_proposal(proposal_id: uuid.UUID, tx: Tx) -> ProposalOut:
    return ProposalOut.of(await synapse.get_proposal(tx, proposal_id))


@router.post("/synapse/proposals/{proposal_id}/items/{index}")
async def decide(proposal_id: uuid.UUID, index: int, body: DecisionIn, tx: Tx) -> dict[str, Any]:
    return await synapse.decide(tx, proposal_id, index, body.accept)


@router.get("/synapse/proposals/{proposal_id}/tasks.md", response_class=PlainTextResponse)
async def tasks(proposal_id: uuid.UUID, tx: Tx) -> str:
    return synapse.tasks_markdown(await synapse.get_proposal(tx, proposal_id))
