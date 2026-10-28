# Go-live: the engine and the market-data service, both directions

Checklist for connecting a deployed engine to a deployed market-data service (z-service,
branch `feat/web-ui` or later). Nothing in either system is specific to the other: the
engine pulls with a generic HTTP connector (a template) and reports back with signed
CloudEvents; the service receives with its generic inbound-events endpoint (a sender is a
line of configuration).

Placeholders: `https://zs.example.com` (the service), `https://engine.example.com` (the
engine). Order matters: each step only needs what the steps above it created, and the
service's `ZS_EVENT_SENDERS` is set last.

## What was already proven end to end (local, real exports)

| Check | Result |
|--|--|
| Connector sync of all 9 exports (4 timeframes × 2 parts + formula) | 9 dataset versions in 73 s, 0 value differences from the CSV files |
| `markets.uipt-screen` on the synced datasets | 12 s, same candidates and regime as the CSV path |
| Subscription (`*`) and per-request callbacks to `/api/events/inbound/<name>` | every delivery `204`; `v1` (HMAC) and `v1a` (Ed25519) both verified by the service |
| Links in the service's *Inbound events* page | open the run in the engine UI (`?tab=runs&run=`) |
| Engine container stack (app role without `BYPASSRLS`, 2 workers, backup/restore drill) | no double processing; restore matched |

## 1. Service side: a read key for the engine

1. `python3 tools/manage_keys.py new --id engine --name "engine connector" --scopes read --days 180`
   (the key goes to the Keychain; stdout is the public entry only).
2. Append the entry to `ZS_API_KEYS` and redeploy. Check with the key:
   `curl -H "Authorization: Bearer <key>" "https://zs.example.com/api/export?interval=1d&part=1" | head -3`
   → CSV header and rows.

## 2. Engine side: install and the project

1. Install per [runbook.md](runbook.md) (compose, TLS proxy, first superadmin). Check
   `/v1/ready` → `{"status": "ready"}`. `MINDGRID_PUBLIC_URL=https://engine.example.com`
   (event links are built from it). Leave `MINDGRID_OUTBOUND_ALLOW_PRIVATE_HOSTS` empty:
   the service is reached over public https.
2. UI → *Projects* → new project (e.g. slug `markets`).
3. Project → *Secrets* → `connector.zservice.token` = the read key from step 1 (write-only;
   only the last 4 characters are shown afterwards).
4. Project → *Connectors* → *Start from* **zservice-exports**, set
   `base_url = https://zs.example.com`, save, *Sync now*. Expected: 9 datasets
   (`bars-1w-part1` … `formula`), each with a version; a repeat sync with unchanged data
   adds no version.

## 3. Engine side: who receives the results

1. Project → *Events* → add a receiver: name `zservice`,
   URL `https://zs.example.com/api/events/inbound/engine`, types `*` (or `run.*`,
   `connector.synced`). Copy the signing secret (`whsec_…`, shown once).
2. Note the engine's public key: `curl https://engine.example.com/v1/events/keys`
   → `public_key` (`whpk_…`).

## 4. Service side, last: accept the sender

1. Set `ZS_EVENT_SENDERS` = `[{"name": "engine", "secret": "whsec_…", "public_key": "whpk_…"}]`
   and redeploy. Until this is set every inbound event is refused with `404` (safe default).
2. Engine → subscription → *Send test*. Expected: delivery `204` in the engine's delivery
   list, and a `subscription.test` row in the service's *Inbound events* page.

## 5. Acceptance run

| Step | Expected |
|--|--|
| Engine: *Sync now* on the connector | `connector.synced` (and `dataset.updated` per changed dataset) in *Inbound events* |
| Engine: project → *Runs* → run `markets.uipt-screen` | run `done`; `run.completed` in *Inbound events*; its link opens the run in the engine |
| A machine run with a callback: `POST /v1/projects/{id}/runs` `{"playbook": "markets.uipt-screen", "callback_url": "https://zs.example.com/api/events/inbound/engine"}` (API key, scope `run`) | the subscription and the callback both deliver; the service stores each `webhook-id` once |
| Stop the service for a few minutes, run again | deliveries retry (5 s … 24 h); after it is back they arrive in order; nothing is lost |
| Engine: `/admin/events` | no dead deliveries; any dead one can be replayed |

## Rollback and rotation

- Stop receiving: remove the sender from `ZS_EVENT_SENDERS` (the engine sees `404`s, keeps
  retrying, then marks the subscription disabled after 5 dead deliveries in a row); or pause
  the subscription in the engine (*Events* → switch it off).
- Stop pulling: save the connector with *Every* empty (sync on request only), or delete
  the project secret.
- Rotate the read key: issue a second entry in `ZS_API_KEYS`, replace the project secret,
  remove the old entry, redeploy.
- Rotate the subscription secret: create a new subscription, add its secret to the sender
  entry, delete the old subscription.
