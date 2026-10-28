"""Typed views of the lookup functions' rows (built in one place, no casts elsewhere)."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import RowMapping

from .models import TokenKind


@dataclass(frozen=True, slots=True)
class KeyRow:
    id: uuid.UUID
    owner_user_id: uuid.UUID
    public_key: bytes
    scopes: frozenset[str]
    project_ids: tuple[uuid.UUID, ...]
    expires_at: datetime
    revoked: bool
    owner_active: bool

    @classmethod
    def of(cls, m: RowMapping) -> KeyRow:
        row: dict[str, Any] = dict(m)
        return cls(
            id=row["id"],
            owner_user_id=row["owner_user_id"],
            public_key=bytes(row["public_key"]),
            scopes=frozenset(row["scopes"]),
            project_ids=tuple(row["project_ids"] or ()),
            expires_at=row["expires_at"],
            revoked=row["revoked_at"] is not None,
            owner_active=str(row["owner_status"]) == "active",
        )

    def usable(self) -> bool:
        return not self.revoked and self.owner_active and self.expires_at > datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class TokenRow:
    id: uuid.UUID
    api_key_id: uuid.UUID
    kind: TokenKind
    family_id: uuid.UUID
    expires_at: datetime
    spent: bool
    revoked: bool

    @classmethod
    def of(cls, m: RowMapping) -> TokenRow:
        row: dict[str, Any] = dict(m)
        return cls(
            id=row["id"],
            api_key_id=row["api_key_id"],
            kind=TokenKind(row["kind"]),
            family_id=row["family_id"],
            expires_at=row["expires_at"],
            spent=row["used_at"] is not None,
            revoked=row["revoked_at"] is not None,
        )

    def usable_as(self, api_key_id: uuid.UUID, kind: TokenKind) -> bool:
        live = not self.revoked and self.expires_at > datetime.now(UTC)
        return live and self.api_key_id == api_key_id and self.kind == kind
