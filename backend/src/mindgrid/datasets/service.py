"""Create datasets, add versions (skipped when the bytes did not change), read rows back.
Reading needs project view rights; writing needs project manage rights."""

import hashlib
import uuid
from compression import zstd
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core.errors import ApiError
from mindgrid.platform.events import service as events
from mindgrid.platform.tenancy import access

from . import config as dataset_config
from . import events as dataset_events
from . import formats
from .models import Dataset, DatasetVersion

MEDIA = {"csv": "text/csv", "json": "application/json", "ndjson": "application/x-ndjson"}


@dataclass(frozen=True, slots=True)
class Incoming:
    data: bytes
    media_type: str
    records_path: str = ""


async def ensure(
    tx: AsyncSession, project_id: uuid.UUID, name: str, source: str, title: str = ""
) -> Dataset:
    await access.require_project_manage(tx, project_id)
    found = await tx.scalar(
        select(Dataset).where(Dataset.project_id == project_id, Dataset.name == name)
    )
    if found is not None:
        return found
    created = Dataset(project_id=project_id, name=name, source=source, title=title or name)
    tx.add(created)
    await tx.flush()
    return created


async def add_version(tx: AsyncSession, dataset: Dataset, incoming: Incoming) -> tuple[int, bool]:
    """(version, created): the same bytes as the newest version create nothing."""
    if len(incoming.data) > dataset_config.get_settings().max_bytes:
        raise ApiError(413, "dataset.too_large", "dataset file too large")
    digest = hashlib.sha256(incoming.data).hexdigest()
    newest = await _version(tx, dataset.id, dataset.current_version)
    if newest is not None and newest.sha256 == digest:
        return newest.version, False
    try:
        parsed = formats.parse(incoming.data, incoming.media_type, incoming.records_path)
    except (formats.FormatError, ValueError) as err:
        raise ApiError(400, "dataset.unreadable", str(err)[:300]) from err
    dataset.current_version += 1
    tx.add(
        DatasetVersion(
            dataset_id=dataset.id,
            project_id=dataset.project_id,
            version=dataset.current_version,
            media_type=incoming.media_type,
            records_path=incoming.records_path,
            sha256=digest,
            size_bytes=len(incoming.data),
            rows=len(parsed.rows),
            columns=parsed.columns,
            meta=parsed.meta,
            blob=zstd.compress(incoming.data, level=6),
        )
    )
    await tx.flush()
    await _prune(tx, dataset)
    data = dataset_events.DatasetUpdated(
        dataset=dataset.name,
        version=dataset.current_version,
        rows=len(parsed.rows),
        columns=len(parsed.columns),
        source=dataset.source,
        links=events.link(
            f"/v1/projects/{dataset.project_id}/datasets/{dataset.name}/versions",
            f"/projects/{dataset.project_id}?tab=data&dataset={dataset.name}",
        ),
    )
    await events.emit(tx, data, project_id=dataset.project_id, subject=f"datasets/{dataset.id}")
    return dataset.current_version, True


async def _prune(tx: AsyncSession, dataset: Dataset) -> None:
    oldest_kept = dataset.current_version - dataset_config.get_settings().keep_versions
    if oldest_kept > 0:
        await tx.execute(
            delete(DatasetVersion).where(
                DatasetVersion.dataset_id == dataset.id, DatasetVersion.version <= oldest_kept
            )
        )


async def _version(tx: AsyncSession, dataset_id: uuid.UUID, version: int) -> DatasetVersion | None:
    return await tx.scalar(
        select(DatasetVersion).where(
            DatasetVersion.dataset_id == dataset_id, DatasetVersion.version == version
        )
    )


async def by_name(tx: AsyncSession, project_id: uuid.UUID, name: str) -> Dataset:
    await access.require_project_view(tx, project_id)
    found = await tx.scalar(
        select(Dataset).where(Dataset.project_id == project_id, Dataset.name == name)
    )
    if found is None:
        raise ApiError(404, "dataset.not_found", "dataset not found", params={"name": name})
    return found


async def listing(tx: AsyncSession, project_id: uuid.UUID) -> list[Dataset]:
    await access.require_project_view(tx, project_id)
    query = select(Dataset).where(Dataset.project_id == project_id).order_by(Dataset.name)
    return list((await tx.scalars(query)).all())


async def versions(tx: AsyncSession, dataset: Dataset) -> list[DatasetVersion]:
    query = (
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset.id)
        .order_by(DatasetVersion.version.desc())
    )
    return list((await tx.scalars(query)).all())


async def load(
    tx: AsyncSession, dataset: Dataset, version: int | None = None
) -> tuple[DatasetVersion, formats.Parsed]:
    """A version (default: newest) and its rows."""
    row = await _version(tx, dataset.id, version or dataset.current_version)
    if row is None:
        raise ApiError(
            404,
            "dataset.version_not_found",
            "no such dataset version",
            params={"name": dataset.name, "version": version},
        )
    return row, formats.parse(zstd.decompress(row.blob), row.media_type, row.records_path)


async def load_raw(
    tx: AsyncSession, dataset: Dataset, version: int
) -> tuple[DatasetVersion, bytes]:
    """A version and its original bytes (no parsing)."""
    row = await _version(tx, dataset.id, version)
    if row is None:
        raise ApiError(
            404,
            "dataset.version_not_found",
            "no such dataset version",
            params={"name": dataset.name, "version": version},
        )
    return row, zstd.decompress(row.blob)


def describe(row: DatasetVersion) -> dict[str, Any]:
    return {
        "version": row.version,
        "rows": row.rows,
        "columns": row.columns,
        "meta": row.meta,
        "sha256": row.sha256,
        "size_bytes": row.size_bytes,
        "media_type": row.media_type,
        "created_at": row.created_at.isoformat(),
    }
