# Runbook: running the engine in production

Single host with Docker Compose (`deploy/`). Every setting is an environment variable,
listed with its type and default in [config-reference.md](config-reference.md).

## Install

1. Make the env: `python3 tools/make_env.py --public-url https://<your domain>` (macOS). It
   generates the database passwords and `MINDGRID_SECRET_KEY` (64 URL-safe characters, checked
   against every place they are used), keeps them in the Keychain (service `mindgrid`,
   account `prod:<NAME>`; a later run reuses them so the database password keeps matching
   the volume) and copies all variables to the clipboard — paste them into the hosting
   panel, or add `--write deploy/.env`. `--set NAME=VALUE` fills any other variable;
   `deploy/env.full.example` lists every variable with its meaning. Without macOS: copy
   `deploy/env.example` to `deploy/.env` and generate each secret with
   `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`. Keep a copy of
   `MINDGRID_SECRET_KEY` in the team's password manager: stored secrets cannot be read
   without it.
2. `docker compose --env-file deploy/.env -f compose.yaml -f deploy/compose.local.yaml up -d --build` — starts PostgreSQL 18 + pgvector,
   runs the migrations once (`migrate`), then the API (port 8700 on 127.0.0.1) and a worker.
3. Put a TLS reverse proxy in front of `127.0.0.1:8700` (the API sets HSTS and secure
   `__Host-` cookies, so it must be served over https) and keep the `Host` header.
4. First superadmin:
   `docker compose --env-file deploy/.env exec api mindgrid admin create-superadmin --email you@example.com`
   (asks for the password; it is never an argument). In automation, pipe it in:
   `... create-superadmin --email you@example.com --password-stdin < password-file`.
5. Check: `curl https://<host>/v1/health` (process up) and `/v1/ready` (database answers).

The first indexing or semantic search downloads the local models (about 1.8 GB:
EmbeddingGemma-300m and the bge-reranker) into the `models` volume; the API loads them in
the background at start-up. After changing `MINDGRID_EMBED_LOCAL_MODEL`, run
`mindgrid admin reindex --email <superadmin>` (each model has its own vector space).

## Hosting panels (Coolify and the like)

Checked against Coolify's Docker Compose and environment-variable documentation and by
running its exact build and start commands (`--project-directory <repository>`,
`-f <repository>/compose.yaml`, `--env-file`), first deployment and redeployment:

- Compose file: `/compose.yaml`, base directory `/`. Every path in it is relative to the
  repository root, which is what the panel passes as the project directory.
- Variables: paste the output of `tools/make_env.py`. The panel hands containers only the
  variables the compose file names; `compose.yaml` names every application variable
  (generated, checked by the gate).
- Secrets out of the image: set `DB_OWNER_PASSWORD`, `DB_APP_PASSWORD` and
  `MINDGRID_SECRET_KEY` to *not available during build* (Build time), or turn on BuildKit
  build secrets. Build arguments can otherwise appear in image metadata; the image needs no
  secret to build.
- Domain: give it to the `api` service with the container port, e.g.
  `https://mindgrid.example.com:8700` (the port only tells the proxy where to send traffic).
  Nothing is published on the host: the panel's proxy reaches `api` inside the network.
- Database role: the `migrate` service creates the app role (`mindgrid admin
  ensure-app-role`, as the owner) before the migrations and aligns its password on every
  deployment, so no repository file has to sit next to the database. The owner password is
  fixed when the `pgdata` volume is first created: keep `DB_OWNER_PASSWORD` unchanged
  afterwards (tools/make_env.py reuses it).
- `migrate` exits after its work; that is expected. The data stays in the `pgdata` volume
  across builds and redeployments; it goes only with the volume (deleting the resource
  together with its volumes, `docker compose down -v`).

## Roles and data safety

- The database owner (`mindgrid`) runs migrations only. The API and the worker use
  `mindgrid_app`: no superuser, no `BYPASSRLS`, owns nothing — every row is filtered by
  row-level security even if application code has a bug.
- Secrets (provider keys, connector tokens, webhook secrets) are sealed with AES-256-GCM
  under keys derived from `MINDGRID_SECRET_KEY`; they never appear in API responses or logs.

## Upgrade

```
git pull && docker compose --env-file deploy/.env -f compose.yaml -f deploy/compose.local.yaml up -d --build
```
`migrate` runs before the new API and worker start; migrations are tested both ways
(upgrade and downgrade) on every commit.

## Backup and restore

```
# daily (cron): compressed custom-format dump
docker compose --env-file deploy/.env exec -T db pg_dump -U mindgrid -Fc mindgrid > mindgrid-$(date +%F).dump
# restore into an empty database
docker compose --env-file deploy/.env exec -T db pg_restore -U mindgrid -d mindgrid --clean --if-exists < mindgrid-YYYY-MM-DD.dump
```
Keep `deploy/.env` (above all `MINDGRID_SECRET_KEY`) with the backups: without the same
secret, sealed secrets in a restored database cannot be opened. The `models` volume needs
no backup (downloaded again).

## Scaling

| Part | How |
|--|--|
| background work (indexing, runs, syncs, event delivery, Synapse) | `--scale worker=N`: jobs and deliveries are claimed with `SKIP LOCKED`, one in-flight delivery per receiver |
| API | more replicas behind the proxy; sessions, rate limits and nonces live in PostgreSQL, so any replica serves any request |
| search latency | the reranker is CPU-bound and reads the first `MINDGRID_RERANK_MAX_CHARS` (500) characters of `MINDGRID_RECALL_RERANK_CANDIDATES` (10) passages. Measured 26 Oct 2026 on 37 real documents (1,445 chunks, 18 Thai/English questions): hit@5 1.00, MRR 0.95, every off-topic question answered with nothing; one search ~3 s on a laptop (2 threads, low priority), reranking alone 4.4–5.4 s in Docker Desktop with 2 threads and 2.3–2.9 s with 4. Set `MINDGRID_RERANK_THREADS` to the cores the API may use, add API replicas, or set `MINDGRID_RERANK_PROVIDER=none` (0.5 s, hit@5 0.93, off-topic still answered with nothing through the per-model distance cutoff) |
| embeddings | a chunk whose text did not change (new version, copied document) reuses its vector — measured: 503 of 624 chunks reused; per-space HNSW indexes; `MINDGRID_RECALL_EF_SEARCH` trades recall for speed. Indexing speed, measured 25 Oct 2026 on 11 real chunks (2 threads): EmbeddingGemma-300m 1.0 s/chunk, 1.35 GB; Qwen3-Embedding-0.6B 6.2 s/chunk, 2.7–4.3 GB — same eval scores with the reranker (all 1.0 on 12 Thai/English cases) |

`tools/load_test.py` repeats the measurement against any deployment (signed API-key calls).

## A market-data project in one command

`tools/provision_project.py` builds a complete project through the API and is safe to run
again. It creates:
- the project;
- the data service key, stored as an encrypted project secret;
- a connector made from the server's data-service template (every timeframe plus the
  formula sheet, synced hourly) and its first sync;
- every playbook in the catalog, switched on;
- optionally a methodology category (`--doc`);
- optionally an API key for MCP and scripts (`--issue-key`). The private key goes to a
  client profile file with mode 600 and is never printed.

Each playbook then runs once on the synced data.

    backend/.venv/bin/python tools/provision_project.py \
        --server https://<your-domain> --email <admin email> \
        --data-url https://<data service host> \
        --data-key-keychain <service>/<account> --issue-key --profile markets

- **Admin password:** read from `MINDGRID_ADMIN_PASSWORD`, or asked for.
- **Data key:** read from `MINDGRID_DATA_KEY`, a Keychain item, or asked for.
- **Data service auth:** today's data service checks an `X-Pull-Key` header; the tool sets
  the connector up that way.
- **Worker:** the first sync and the runs need the worker service.

## Example projects on live public data

`tools/demo_projects.py` creates six example projects on real open data sources (no keys
needed), and is safe to run again. Each project gets:
- a connector to its source and a first sync;
- exactly its own three playbooks (screens with Thai titles); every other playbook in the
  catalog is switched off for the project, whatever the system switch says;
- a knowledge category of public-domain PDF reports (USGS, NIST, EPA, NASA) and reference
  articles;
- one run of every playbook.

| Project | Data | Playbooks | Use |
|---|---|---|---|
| Seismic Watch | USGS earthquake feed | strong, shallow strong, significant this month | API + Postman |
| Open Source Pulse | GitHub repositories of python, nodejs, rust-lang | most starred, issue backlog, most forked | API + Postman |
| Climate & Emissions | Our World in Data CO2 by country | top emitters, per person, one country's trend | API + Postman |
| Exoplanet Explorer | NASA Exoplanet Archive | Earth-sized, temperate, recent discoveries | web |
| City Weather Risk | Open-Meteo 16-day forecasts, five Thai cities | heat stress, heavy rain, high UV | web |
| Thai Air Quality | Open-Meteo hourly PM2.5 / PM10 / US AQI, five Thai cities | PM2.5 over the Thai standard, unhealthy hours, clean-air hours | web |

The API projects also get a read+run key limited to the project, a client profile and a
Postman environment with a sample question for the project's documents. Import the
environment together with `docs/postman/api.postman_collection.json` (see
[postman/README.md](postman/README.md)). A later run refreshes the environment and keeps
its key.

    backend/.venv/bin/python tools/demo_projects.py --server https://<your-domain> \
        --email <admin email> [--only <slug>]

## Running a project's playbooks many times

`tools/run_playbooks.py` runs every playbook switched on in a project N times (1-50) on the
project's own data, one run at a time; each is a real run with its inputs and outputs, so
the dashboard and the results history fill with real use. Playbooks with `top_n` cycle
through 10, 20, 30 and 50 rows.

    backend/.venv/bin/python tools/run_playbooks.py --server https://<your-domain> \
        --email <admin email> --project us-stock-radar --times 15

## Keeping a playbook family in its projects

The system switch ("Assigned to all projects") puts a playbook in every project, including
ones made later. `tools/playbook_scope.py` keeps a family (an id prefix) only where it
belongs: projects outside `--keep` get their own "off", `--keep` projects keep an own "on",
and the family's system switch goes off. Nothing is deleted; without `--apply` it only
prints the plan.

    backend/.venv/bin/python tools/playbook_scope.py --server https://<your-domain> \
        --email <admin email> --prefix markets. --keep us-stock-radar [--apply]

## Rotating the server secret

Changing `MINDGRID_SECRET_KEY` signs everyone out, invalidates CSRF tokens, changes the
event signing key (receivers re-read `GET /v1/events/keys`) and makes sealed secrets
unreadable: set provider keys, connector tokens and webhook subscriptions again afterwards.

## Monitoring

- Logs are JSON lines on stdout (`docker compose logs api worker`), one `request_id` per
  request (also in the `X-Request-ID` response header).
- Watch: `/v1/ready`, `job.failed` and dead deliveries (UI → Events), connector `last_status`,
  Synapse `last_error`.
- The audit log (UI → Logs) records sign-ins, key use, overrides and every change of rights.
