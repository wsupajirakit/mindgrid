"""Sliding-window rate limits shared by every API replica (rows in the UNLOGGED table
`rate_hits`; no extra service). Old rows are deleted as they fall out of the window."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def hit(tx: AsyncSession, key: str, limit: int, window_s: int) -> int | None:
    """Record one attempt for `key`; return seconds to wait when over the limit."""
    # One writer per key at a time, so concurrent attempts cannot overshoot the limit.
    await tx.execute(text("select pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": key})
    now = datetime.now(UTC)
    since = now - timedelta(seconds=window_s)
    await tx.execute(
        text("delete from rate_hits where key = :k and at <= :s"), {"k": key, "s": since}
    )
    rows = (
        (
            await tx.execute(
                text("select at from rate_hits where key = :k order by at limit :n"),
                {"k": key, "n": limit},
            )
        )
        .scalars()
        .all()
    )
    if len(rows) >= limit:
        oldest: datetime = rows[0]
        return max(1, int((oldest + timedelta(seconds=window_s) - now).total_seconds()) + 1)
    await tx.execute(
        text("insert into rate_hits (key, at) values (:k, :at)"), {"k": key, "at": now}
    )
    return None
