# Events: receiving results from the engine

One pipeline for every project and every feature. Nothing in it is specific to a receiver:
any system that accepts an HTTPS POST can subscribe, and any number of receivers can.

## Two ways to receive

| | Subscription | Callback |
|--|--|--|
| Who sets it up | a project manager (project scope) or a superadmin (every project) | whoever makes the request |
| What it gets | every event of the chosen types (`run.completed`, `run.*`, `*`) | the outcome of that one request |
| Signature | `v1` (HMAC with the subscription secret) **and** `v1a` (server key) | `v1a` (server key) |
| How | UI → project → *Events*, or `POST /v1/projects/{id}/event-subscriptions` | add `callback_url` to the request |

Requests that take `callback_url`: start a run (`POST /v1/projects/{id}/runs`), upload a
document (form field), sync a connector, run an eval, ask for an answer.

## The message

`POST <your URL>` with `Content-Type: application/cloudevents+json` — a CloudEvents 1.0
event in structured mode:

```json
{
  "specversion": "1.0",
  "id": "01a1...",
  "source": "https://engine.example.com/v1/projects/<project id>",
  "type": "run.completed",
  "subject": "runs/<run id>",
  "time": "2026-10-25T14:00:00+00:00",
  "datacontenttype": "application/json",
  "dataschema": "https://engine.example.com/v1/events/types/run.completed",
  "data": {
    "run_id": "…", "playbook_id": "markets.uipt-screen", "playbook_version": 1,
    "playbook_status": "active", "status": "done", "error": "", "outputs": ["candidates", "regime"],
    "links": {"api": "https://engine.example.com/v1/runs/<run id>",
              "ui": "https://engine.example.com/projects/<project id>?tab=runs&run=<run id>"}
  }
}
```

Events are **thin**: identifiers, status and links. Read the full result through
`links.api` (with an API key) or open `links.ui` in a browser. Every type and its data
schema: `GET /v1/events/types` (public).

| Type | When |
|--|--|
| `run.completed`, `run.failed` | a playbook run ended |
| `document.indexed` | a document version is searchable by meaning |
| `dataset.updated` | a dataset has a new version |
| `connector.synced` | a connector sync finished |
| `eval.completed` | a retrieval eval finished |
| `eval.judged` | an LLM finished grading an eval run |
| `answer.completed` | a server-written answer is ready |
| `job.failed` | any background job gave up after its retries |
| `subscription.test` | the *Send test* button |

## Headers and verification (Standard Webhooks)

| Header | Value |
|--|--|
| `webhook-id` | the event id — the same on every retry: use it to ignore duplicates |
| `webhook-timestamp` | Unix seconds — refuse messages more than 5 minutes off your clock |
| `webhook-signature` | space-separated signatures: `v1,<base64>` and/or `v1a,<base64>` |

Signed content: `<webhook-id>.<webhook-timestamp>.<raw body>` (verify the raw bytes;
do not re-serialise the JSON).

- `v1`: HMAC-SHA256 with the subscription secret (`whsec_` + base64, shown once when the
  subscription is created).
- `v1a`: Ed25519 with the server's event key, published at `GET /v1/events/keys`
  (`whpk_` + base64 of the raw 32-byte key).

Any Standard Webhooks library verifies `v1`. In Python without one:

```python
import base64, hashlib, hmac, time


def verify(secret: str, headers: dict[str, str], body: bytes, tolerance: int = 300) -> bool:
    msg_id, stamp = headers["webhook-id"], int(headers["webhook-timestamp"])
    if abs(time.time() - stamp) > tolerance:
        return False
    key = base64.b64decode(secret.removeprefix("whsec_"))
    want = (
        "v1,"
        + base64.b64encode(
            hmac.new(key, f"{msg_id}.{stamp}.".encode() + body, hashlib.sha256).digest()
        ).decode()
    )
    return any(hmac.compare_digest(want, s) for s in headers["webhook-signature"].split())
```

## Delivery rules

- Answer `2xx` within 15 seconds (queue the work, then answer).
- Anything else is retried: after 5 s, 5 min, 30 min, 2 h, 5 h, 10 h, 14 h, 20 h and 24 h
  (with jitter; a `Retry-After` header is respected). After the last try the delivery is
  **dead** — kept, visible in the UI and replayable.
- `410 Gone` stops at once and switches the subscription off; so do 5 dead deliveries in a
  row. Switch it back on in the UI.
- Redirects are not followed. Receivers must be HTTPS on a public address unless the
  operator allows the host (`MINDGRID_OUTBOUND_ALLOW_PRIVATE_HOSTS`).
- Each receiver has its own queue (one delivery in flight at a time), so a slow or broken
  receiver never delays another; order is by time but not guaranteed — use `time` and
  `webhook-id`.
