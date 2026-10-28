"""/v1/projects/{id}/datasets and /v1/projects/{id}/connectors: versioned datasets (upload
or connector), row previews, generic connectors (templates, save, sync now)."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, Form, Path, Query, UploadFile
from pydantic import BaseModel, Field

from mindgrid.bridges.connectors import service as connectors
from mindgrid.bridges.connectors.models import Connector
from mindgrid.bridges.connectors.spec import ConnectorSpec
from mindgrid.datasets import service as datasets
from mindgrid.datasets.models import NAME, Dataset

from .deps import Tx

router = APIRouter(tags=["data"])
PREVIEW_MAX = 500


class DatasetOut(BaseModel):
    id: uuid.UUID
    name: str
    title: str
    source: str
    current_version: int
    updated_at: datetime

    @classmethod
    def of(cls, d: Dataset) -> DatasetOut:
        return cls.model_validate(d, from_attributes=True)


class ConnectorIn(BaseModel):
    spec: ConnectorSpec
    every_minutes: int | None = Field(None, ge=1, le=7 * 24 * 60)


class ConnectorOut(BaseModel):
    id: uuid.UUID
    name: str
    spec: dict[str, Any]
    enabled: bool
    every_minutes: int | None
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_status: str
    last_error: str
    last_changed: list[str]

    @classmethod
    def of(cls, c: Connector) -> ConnectorOut:
        return cls.model_validate(c, from_attributes=True)


@router.get("/projects/{project_id}/datasets")
async def list_datasets(project_id: uuid.UUID, tx: Tx) -> list[DatasetOut]:
    return [DatasetOut.of(d) for d in await datasets.listing(tx, project_id)]


@router.get("/projects/{project_id}/datasets/{name}/versions")
async def dataset_versions(project_id: uuid.UUID, name: str, tx: Tx) -> list[dict[str, Any]]:
    found = await datasets.by_name(tx, project_id, name)
    return [datasets.describe(v) for v in await datasets.versions(tx, found)]


class RowsQuery(BaseModel):
    version: int | None = Field(None, ge=1)
    limit: int = Field(50, ge=1, le=PREVIEW_MAX)
    offset: int = Field(0, ge=0)


@router.get("/projects/{project_id}/datasets/{name}/rows")
async def dataset_rows(
    project_id: uuid.UUID, name: str, q: Annotated[RowsQuery, Query()], tx: Tx
) -> dict[str, Any]:
    found = await datasets.by_name(tx, project_id, name)
    row, parsed = await datasets.load(tx, found, q.version)
    return {**datasets.describe(row), "items": parsed.rows[q.offset : q.offset + q.limit]}


@router.post("/projects/{project_id}/datasets/{name}", status_code=201)
async def upload_dataset(
    project_id: uuid.UUID,
    name: Annotated[str, Path(pattern=NAME)],
    tx: Tx,
    file: Annotated[UploadFile, File()],
    format: Annotated[Literal["csv", "json", "ndjson"], Form()] = "csv",
    records_path: Annotated[str, Form(max_length=200)] = "",
) -> dict[str, Any]:
    dataset = await datasets.ensure(tx, project_id, name, "upload")
    incoming = datasets.Incoming(await file.read(), datasets.MEDIA[format], records_path)
    version, created = await datasets.add_version(tx, dataset, incoming)
    return {"name": name, "version": version, "created": created}


@router.get("/connector-templates")
def connector_templates() -> list[dict[str, Any]]:
    return connectors.templates()


@router.get("/projects/{project_id}/connectors")
async def list_connectors(project_id: uuid.UUID, tx: Tx) -> list[ConnectorOut]:
    return [ConnectorOut.of(c) for c in await connectors.listing(tx, project_id)]


@router.put("/projects/{project_id}/connectors/{name}")
async def save_connector(
    project_id: uuid.UUID, name: Annotated[str, Path(pattern=NAME)], body: ConnectorIn, tx: Tx
) -> ConnectorOut:
    saved = await connectors.save(tx, project_id, name, body.spec, body.every_minutes)
    return ConnectorOut.of(saved)


class SyncIn(BaseModel):
    callback_url: str | None = Field(
        None, max_length=2000, description="Receives connector.synced or job.failed."
    )


@router.post("/connectors/{connector_id}/sync", status_code=202)
async def sync_connector(
    connector_id: uuid.UUID, tx: Tx, body: SyncIn | None = None
) -> dict[str, str]:
    await connectors.request_sync(tx, connector_id, body.callback_url if body else None)
    return {"status": "queued"}
