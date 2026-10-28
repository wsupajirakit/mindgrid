"""/v1/categories/{id}/documents and /v1/documents/{id}: upload (multipart), list, read,
chunk preview, trust tag, remove. Category rights decide every step."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Query, UploadFile
from pydantic import BaseModel

from mindgrid.knowledge.index import events as index_events
from mindgrid.knowledge.library import graph as knowledge_graph
from mindgrid.knowledge.library import service as library
from mindgrid.knowledge.library.models import Document, Trust
from mindgrid.platform.events import service as events
from mindgrid.platform.tenancy.models import Level

from .deps import Tx

router = APIRouter(tags=["knowledge"])
PREVIEW_MAX = 200


class DocumentOut(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    title: str
    trust: Trust
    source: str
    current_version: int
    updated_at: datetime

    @classmethod
    def of(cls, d: Document) -> DocumentOut:
        return cls(
            id=d.id,
            category_id=d.category_id,
            title=d.title,
            trust=d.trust,
            source=d.source,
            current_version=d.current_version,
            updated_at=d.updated_at,
        )


class ChunkOut(BaseModel):
    ordinal: int
    heading: str
    text: str
    location: dict[str, Any]


class TrustBody(BaseModel):
    trust: Trust


CALLBACK = "Receives document.indexed or job.failed for this document (signed, see /v1/events)."


@router.post("/categories/{category_id}/documents", status_code=201)
async def upload(
    category_id: uuid.UUID,
    tx: Tx,
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form(max_length=300)] = "",
    trust: Annotated[Trust, Form()] = Trust.UNRATED,
    callback_url: Annotated[str | None, Form(max_length=2000, description=CALLBACK)] = None,
) -> DocumentOut:
    data = await file.read()
    upload_in = library.Upload(
        filename=file.filename or "upload.txt", data=data, title=title, trust=trust
    )
    doc = await library.add_document(tx, category_id, upload_in)
    if callback_url:
        await events.register_callback(
            tx, f"documents/{doc.id}", doc.project_id, callback_url, index_events.OUTCOMES
        )
    return DocumentOut.of(doc)


@router.get("/categories/{category_id}/documents")
async def list_documents(category_id: uuid.UUID, tx: Tx) -> list[DocumentOut]:
    return [DocumentOut.of(d) for d in await library.list_documents(tx, category_id)]


@router.get("/documents/{document_id}")
async def get_document(document_id: uuid.UUID, tx: Tx) -> DocumentOut:
    return DocumentOut.of(await library.get_document(tx, document_id, Level.READ))


@router.get("/documents/{document_id}/chunks")
async def chunks(
    document_id: uuid.UUID, tx: Tx, limit: int = Query(default=20, ge=1, le=PREVIEW_MAX)
) -> list[ChunkOut]:
    found = await library.chunk_preview(tx, document_id, limit)
    return [
        ChunkOut(ordinal=c.ordinal, heading=c.heading, text=c.text, location=c.location)
        for c in found
    ]


@router.put("/documents/{document_id}/trust", status_code=204)
async def set_trust(document_id: uuid.UUID, body: TrustBody, tx: Tx) -> None:
    await library.set_trust(tx, document_id, body.trust)


@router.delete("/documents/{document_id}", status_code=204)
async def remove(document_id: uuid.UUID, tx: Tx) -> None:
    await library.remove_document(tx, document_id)


class GraphOut(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


@router.get("/projects/{project_id}/knowledge-graph")
async def knowledge_network(project_id: uuid.UUID, tx: Tx) -> GraphOut:
    """The project's knowledge as a network: categories, documents (sized by chunks) and
    links between documents that questions found together."""
    found = await knowledge_graph.build(tx, project_id)
    return GraphOut(nodes=found.nodes, edges=found.edges)
