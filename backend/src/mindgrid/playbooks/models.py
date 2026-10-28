"""Custom playbook specs (shipped ones live in code), overrides per system or project
(switch off, pin a version, override parameters) and translated titles and summaries."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mindgrid.core.settings_registry import Scope
from mindgrid.db.base import Base, Keyed
from mindgrid.platform.settings.models import SCOPE_ENUM

from .spec import Status


def _values(members: type[Status]) -> list[str]:
    return [m.value for m in members]


class CustomPlaybook(Base):
    __tablename__ = "custom_playbooks"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[Status] = mapped_column(
        Enum(Status, name="playbook_status", values_callable=_values)
    )
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_by: Mapped[uuid.UUID | None] = mapped_column(server_default=text("mindgrid_actor()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlaybookOverride(Keyed, Base):
    __tablename__ = "playbook_overrides"
    __table_args__ = (
        Index(
            "uq_playbook_overrides_target",
            "scope",
            text("coalesce(scope_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            "playbook_id",
            unique=True,
        ),
    )

    scope: Mapped[Scope] = mapped_column(SCOPE_ENUM)  # system or project
    scope_id: Mapped[uuid.UUID | None]
    playbook_id: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int | None] = mapped_column(Integer)  # None = newest runnable
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(server_default=text("mindgrid_actor()"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PlaybookTranslation(Base):
    """A playbook's title and summary in one language (wins over the text its spec ships)."""

    __tablename__ = "playbook_translations"

    playbook_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    locale: Mapped[str] = mapped_column(String(8), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(String(2000))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(server_default=text("mindgrid_actor()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
