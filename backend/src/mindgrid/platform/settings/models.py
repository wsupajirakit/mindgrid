"""Stored setting values and sealed secrets, both keyed by scope. A system-scope row has
no scope id; every other scope names its user, project or category (unique with NULLs
treated as equal, PostgreSQL 15+)."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    LargeBinary,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mindgrid.core.settings_registry import Scope
from mindgrid.db.base import Base, Keyed


def _values(members: type[enum.StrEnum]) -> list[str]:
    return [m.value for m in members]


SCOPE_ENUM = Enum(Scope, name="setting_scope", values_callable=_values)
_SCOPE_ID_RULE = "(scope = 'system') = (scope_id is null)"


class SettingValue(Keyed, Base):
    __tablename__ = "setting_values"
    __table_args__ = (
        CheckConstraint(_SCOPE_ID_RULE, name="scope_id_rule"),
        UniqueConstraint(
            "scope",
            "scope_id",
            "key",
            name="uq_setting_values_scope_key",
            postgresql_nulls_not_distinct=True,
        ),
    )

    scope: Mapped[Scope] = mapped_column(SCOPE_ENUM)
    scope_id: Mapped[uuid.UUID | None]
    key: Mapped[str] = mapped_column(String(64))
    value: Mapped[Any] = mapped_column(JSONB)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(server_default=text("mindgrid_actor()"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SecretValue(Keyed, Base):
    __tablename__ = "secret_values"
    __table_args__ = (
        CheckConstraint(_SCOPE_ID_RULE, name="scope_id_rule"),
        UniqueConstraint(
            "scope",
            "scope_id",
            "name",
            name="uq_secret_values_scope_name",
            postgresql_nulls_not_distinct=True,
        ),
    )

    scope: Mapped[Scope] = mapped_column(SCOPE_ENUM)
    scope_id: Mapped[uuid.UUID | None]
    name: Mapped[str] = mapped_column(String(64))
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    nonce: Mapped[bytes] = mapped_column(LargeBinary)
    key_version: Mapped[int] = mapped_column(SmallInteger)
    hint: Mapped[str] = mapped_column(String(8))  # last characters, for recognition only
    updated_by: Mapped[uuid.UUID | None] = mapped_column(server_default=text("mindgrid_actor()"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
