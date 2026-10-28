"""Shared rate-limit hits (a plain table: no key, no row-level security, app role may
only insert, read and delete)."""

from sqlalchemy import Column, DateTime, Index, Table, Text

from mindgrid.db.base import Base

rate_hits = Table(
    "rate_hits",
    Base.metadata,
    Column("key", Text, nullable=False),
    Column("at", DateTime(timezone=True), nullable=False),
    Index("ix_rate_hits_key_at", "key", "at"),
    prefixes=["UNLOGGED"],
)
