"""Deliver due events: claim a batch (one in-flight delivery per subscription, so a slow
receiver never holds up another), POST the CloudEvents JSON with Standard Webhooks
headers, and record the outcome. 2xx = delivered; 410 = dead and the subscription is
switched off; anything else is retried on the schedule (Retry-After respected), then dead."""

import asyncio
import json
import random
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import httpx
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from mindgrid.core import netguard
from mindgrid.db.session import SYSTEM, transaction
from mindgrid.platform.jobs import handlers

from . import config as event_config
from . import service, signing

log = structlog.get_logger(__name__)
LEASE = timedelta(minutes=2)
PARALLEL = 8
HTTP_GONE = 410


@dataclass(frozen=True, slots=True)
class Outcome:
    ok: bool
    code: int | None = None
    error: str = ""
    retry_after: float | None = None
    gone: bool = False
    final: bool = False


def _retry_delay(attempts: int, outcome: Outcome) -> timedelta | None:
    schedule = [float(s) for s in event_config.get_settings().retry_seconds]
    if outcome.ok or outcome.gone or outcome.final or attempts > len(schedule):
        return None
    wait = schedule[attempts - 1] * random.uniform(0.9, 1.1)  # noqa: S311 — jitter only
    return timedelta(seconds=max(wait, outcome.retry_after or 0))


def _headers(row: dict[str, Any], body: bytes) -> dict[str, str]:
    msg_id, stamp = str(row["event_id"]), int(time.time())
    signatures = [signing.ed25519_v1a(msg_id, stamp, body)]
    if row["subscription_id"] is not None:
        secret = service.open_secret(
            row["subscription_id"],
            row["secret_ciphertext"],
            row["secret_nonce"],
            row["secret_version"],
        )
        signatures.insert(0, signing.hmac_v1(secret, msg_id, stamp, body))
    return {
        "content-type": "application/cloudevents+json; charset=utf-8",
        "webhook-id": msg_id,
        "webhook-timestamp": str(stamp),
        "webhook-signature": " ".join(signatures),
        "user-agent": "mindgrid-events/1",
    }


def _retry_after(response: httpx.Response) -> float | None:
    try:
        return float(response.headers.get("retry-after", ""))
    except ValueError:
        return None


async def send(client: httpx.AsyncClient, row: dict[str, Any]) -> Outcome:
    body = json.dumps(service.envelope(row), separators=(",", ":")).encode()
    try:
        await netguard.check(row["url"])
        response = await client.post(row["url"], content=body, headers=_headers(row, body))
    except netguard.BlockedTargetError as err:
        return Outcome(False, error=str(err), final=True)
    except httpx.HTTPError as err:
        return Outcome(False, error=f"{type(err).__name__}: {err}"[:300])
    code = response.status_code
    if 200 <= code < 300:
        return Outcome(True, code)
    return Outcome(False, code, f"HTTP {code}", _retry_after(response), gone=code == HTTP_GONE)


async def _record(tx: AsyncSession, row: dict[str, Any], worker: str, outcome: Outcome) -> None:
    retry = _retry_delay(int(row["attempts"]), outcome)
    await tx.execute(
        text(
            "select mindgrid_delivery_result(:id, :worker, :ok, :code, :error, :retry,"
            " :gone, :after)"
        ),
        {
            "id": row["delivery_id"],
            "worker": worker,
            "ok": outcome.ok,
            "code": outcome.code,
            "error": outcome.error,
            "retry": retry,
            "gone": outcome.gone,
            "after": event_config.get_settings().disable_after_dead,
        },
    )


async def run_once(worker: str) -> int:
    cfg = event_config.get_settings()
    async with transaction(SYSTEM) as tx:
        rows = [
            dict(r)
            for r in (
                await tx.execute(
                    text("select * from mindgrid_claim_deliveries(:worker, :lease, :limit)"),
                    {"worker": worker, "lease": LEASE, "limit": cfg.batch},
                )
            ).mappings()
        ]
    if not rows:
        return 0
    gate = asyncio.Semaphore(PARALLEL)

    async def one(client: httpx.AsyncClient, row: dict[str, Any]) -> tuple[dict[str, Any], Outcome]:
        async with gate:
            return row, await send(client, row)

    async with httpx.AsyncClient(timeout=cfg.timeout_seconds, follow_redirects=False) as client:
        results = await asyncio.gather(*(one(client, r) for r in rows))
    async with transaction(SYSTEM) as tx:
        for row, outcome in results:
            await _record(tx, row, worker, outcome)
    log.info("events.delivered", count=len(rows), ok=sum(1 for _, o in results if o.ok))
    return len(rows)


_WORKER = f"events-{random.getrandbits(32):08x}"


async def _deliver_task() -> None:
    while await run_once(_WORKER) >= event_config.get_settings().batch:
        pass  # a full batch: more may be due


async def _purge_task() -> None:
    async with transaction(SYSTEM) as tx:
        await tx.execute(
            text("select mindgrid_purge_events(:days)"),
            {"days": event_config.get_settings().keep_days},
        )


handlers.every("events.deliver", event_config.get_settings().every_seconds, _deliver_task)
handlers.every("events.purge", 3600, _purge_task)
