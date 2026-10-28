"""API keys (public part only), issued tokens (hashes only) and seen nonces."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Table,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from mindgrid.db.base import Base, Keyed


def _values(members: type[enum.StrEnum]) -> list[str]:
    return [m.value for m in members]


class KeyScope(enum.StrEnum):
    READ = "read"  # GET
    RUN = "run"  # run playbooks / ask (POST to run endpoints)
    EDIT = "edit"  # every other write


class TokenKind(enum.StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class ApiKey(Keyed, Base):
    __tablename__ = "api_keys"

    key_id: Mapped[str] = mapped_column(String(40), unique=True)  # public, e.g. mgk_...
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    public_key: Mapped[bytes] = mapped_column(LargeBinary)  # raw Ed25519, 32 bytes
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text))
    # Empty = every project the owner may use; otherwise only these.
    project_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid(as_uuid=True)))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(server_default=text("mindgrid_actor()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApiToken(Keyed, Base):
    __tablename__ = "api_tokens"
    __table_args__ = (Index("ix_api_tokens_family_id", "family_id"),)

    api_key_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("api_keys.id", ondelete="CASCADE"))
    kind: Mapped[TokenKind] = mapped_column(
        Enum(TokenKind, name="token_kind", values_callable=_values)
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    family_id: Mapped[uuid.UUID]  # one sign-in = one family; refresh reuse kills it
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # refresh: spent
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# One-time nonces of signed requests (no row-level security; pruned past the window).
request_nonces = Table(
    "request_nonces",
    Base.metadata,
    Column("key_id", String(40), primary_key=True),
    Column("nonce", String(64), primary_key=True),
    Column("seen_at", DateTime(timezone=True), nullable=False),
    prefixes=["UNLOGGED"],
)
