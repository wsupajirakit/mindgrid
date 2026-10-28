"""Datasets and their versions. Every row carries its project for row-level security."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mindgrid.db.base import Base, Keyed, Timestamped

NAME = r"^[a-z0-9][a-z0-9_.-]{0,99}$"


class Dataset(Keyed, Timestamped, Base):
    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_datasets_project_name"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))  # stable reference, e.g. "bars-1d-part1"
    title: Mapped[str] = mapped_column(String(200), default="")
    source: Mapped[str] = mapped_column(String(120), default="upload")  # upload | connector:<id>
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(server_default=text("mindgrid_actor()"))


class DatasetVersion(Keyed, Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (
        UniqueConstraint("dataset_id", "version", name="uq_dataset_versions_dataset_version"),
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    media_type: Mapped[str] = mapped_column(String(100))  # text/csv | application/json | ...
    # JSON: where the records are inside the file (dot path); reading a version needs it.
    records_path: Mapped[str] = mapped_column(String(200), default="", server_default="")
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    rows: Mapped[int] = mapped_column(Integer)
    columns: Mapped[list[str]] = mapped_column(JSONB)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB)  # leading "# key: value" lines etc.
    blob: Mapped[bytes] = mapped_column(LargeBinary)  # zstd-compressed original bytes
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
