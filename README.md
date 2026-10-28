# MindGrid — RAG Engine for Knowledge & Playbooks

MindGrid is a self-hosted **RAG (retrieval-augmented generation) engine**. It gives people,
scripts and AI assistants one governed place to **ask questions about a project's documents**
and to **run repeatable analyses on its live data**.

Two rules shape the whole system:

1. **Answers must cite their sources.** Every answer points at the passages it used (`[P1]`,
   `[P2]`), and a checker flags any line that cites nothing or cites a passage that does not
   exist.
2. **Numbers come from code, never from a model.** Screens, rankings and figures are produced
   by versioned *playbooks* that run real functions on real data, so the same input always
   gives the same result.

## What a project contains

Work is organised in **projects**. Each project has its own members, documents, data and
playbooks, and nothing leaks between projects.

- **Knowledge** — documents (PDF, Word, Markdown, text, CSV) sorted into categories, some of
  which can be restricted to chosen people or groups.
- **Data** — datasets filled by connectors that fetch CSV or JSON from any HTTP source on a
  schedule; a new version is stored only when the bytes change.
- **Playbooks** — analyses described as JSON: a short chain of registered functions (read a
  dataset, filter, rank, compute indicators…). Versions are immutable and every run pins the
  exact dataset versions it read, so any result can be replayed later.
- **Answers and runs** — every question, answer, playbook run and report from an AI client is
  kept in one history, with who asked and what was used.

The knowledge part is optional: a project made only of data and playbooks works on its own.

## How answers are grounded

Retrieval is **hybrid**: semantic vectors (a local EmbeddingGemma model), BM25 full-text and
trigram matching (which handles Thai text well), fused with reciprocal rank fusion and
re-ordered by a cross-encoder reranker. A measured relevance cut-off lets the engine say "the
documents do not cover this" instead of guessing.

Quality is **measured, not assumed**: golden question sets report hit@k, recall, MRR, nDCG and
correct abstentions, with an optional model-based judge. Vectors are reused by content hash
across document versions, so an unchanged section is never embedded twice.

## Ways in

| Client | How it connects |
| --- | --- |
| Web console | React app in Thai, English and Italian, light and dark |
| HTTP API | REST with a published OpenAPI description |
| AI assistants | MCP server: recall passages, check citations, run playbooks |
| Command line | CLI for scripts and terminals |
| Postman | Ready-made collection that signs every request |
| Other systems | Outgoing and incoming events (CloudEvents over Standard Webhooks) |

## Security

- **Rules live in the database.** Every access rule is one SQL function used by both the API
  and PostgreSQL row-level security, so the two can never disagree. Roles come from a
  person's own role or from their groups (a personal role always wins).
- **Machine access is signed.** API keys sign each request with Ed25519 (HTTP Message
  Signatures, RFC 9421, plus a body digest) within a short time window and with one-time
  nonces, then exchange for short-lived tokens with rotation and reuse detection.
- **People** sign in with Argon2id-hashed passwords (at least 9 characters with lower-case,
  upper-case and a digit); sessions use `__Host-` cookies with CSRF protection and sign-in
  attempts are rate-limited.
- **Secrets** (connector keys, tokens) are sealed with AES-256-GCM; connectors cannot reach
  private network addresses and never follow redirects.

## Learning from a source repository

**Synapse** watches a source code repository. When new commits arrive it turns them into
proposals — new knowledge, updated rules, measured results — with personal details and keys
stripped out, and a person accepts or rejects each item.

## Example projects

Provisioning tools build complete projects on live public data in one command — earthquakes
(USGS), open-source activity (GitHub), climate (Our World in Data), exoplanets (NASA), weather
and air quality for Thai cities (Open-Meteo) — each with its own playbooks, PDF references and,
for API use, a key and a Postman environment. A markets pack reproduces an existing stock
screening pipeline as playbooks, proven identical by a parity test.

## Architecture

| Part | Folder |
| --- | --- |
| Identity, projects and rights, audit, settings, sealed secrets, API keys, jobs, events | `backend/src/mindgrid/platform` |
| Document intake, library, hybrid recall, answers, evaluations | `backend/src/mindgrid/knowledge` |
| Functions, playbooks and runs | `backend/src/mindgrid/{functions,playbooks,runs}` |
| Datasets and HTTP connectors | `backend/src/mindgrid/{datasets,bridges}` |
| Embedding, reranking and answer-writing providers | `backend/src/mindgrid/providers` |
| Synapse | `backend/src/mindgrid/synapse` |
| Packs (installed as separate packages) | `backend/packs` |
| Web console | `web` |
| Container image and compose files | `deploy`, `compose.yaml` |

**Stack:** Python 3.14 · FastAPI · SQLAlchemy 2 (async) · PostgreSQL 18 with pgvector ·
Alembic · React 19 · Vite · TanStack Router/Query/Table · Radix · Tailwind 4 · Paraglide ·
Docker Compose (database, migrations, API, worker).

## Running it

```bash
docker compose --env-file deploy/.env up -d
```

`tools/make_env.py` generates the environment file; every setting is documented in
[docs/config-reference.md](docs/config-reference.md) and operations (install, backup,
scaling, key rotation) in [docs/runbook.md](docs/runbook.md).

For development (Python 3.14, [uv](https://docs.astral.sh/uv/), PostgreSQL 18 with pgvector):

```bash
cd backend && uv sync
uv run --project backend uvicorn --factory mindgrid.app:create_app --port 8700
cd web && npm ci && npm run dev
```

## Quality

One gate runs before every change: ruff, pyright in strict mode, module size limits, checks
for private data in the code, a migration down-and-up round trip, the backend test suite
against a real PostgreSQL database, the OpenAPI and Postman files kept in sync, and the web
checks (types, lint, translations, tests, build and bundle budget).

## Documentation

| Topic | Document |
| --- | --- |
| Running it in production | [docs/runbook.md](docs/runbook.md) |
| Every environment variable | [docs/config-reference.md](docs/config-reference.md) |
| Access rules, roles and groups | [docs/access.md](docs/access.md) |
| Calling the API with a key | [docs/api-keys.md](docs/api-keys.md) |
| Postman collection | [docs/postman](docs/postman) |
| CLI and MCP | [docs/cli-and-mcp.md](docs/cli-and-mcp.md) |
| Playbooks | [docs/playbooks.md](docs/playbooks.md) |
| Events and callbacks | [docs/events.md](docs/events.md) |
| Optional model steps (contextual chunks, query rewrite, judge) | [docs/llm-steps.md](docs/llm-steps.md) |
| Markets pack | [docs/markets-pack.md](docs/markets-pack.md) |
| Synapse | [docs/synapse.md](docs/synapse.md) |
