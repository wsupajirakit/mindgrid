# Configuration reference

Generated from the Settings classes by `tools/config_reference.py`; do not edit by hand.
A blank value means the default; a malformed value stops the boot with the variable named.

## ConnectorSettings (`mindgrid.bridges.connectors.config`)

Connector schedule rules (network rules: core.netguard).

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_CONNECTOR_MIN_EVERY_MINUTES` | int | `5` | Shortest schedule interval. |

## BrandSettings (`mindgrid.core.brand`)

The displayed product name and look, changeable from this one place.

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_BRAND_NAME` | str | `MindGrid` | Displayed product name. |
| `MINDGRID_BRAND_SHORT_NAME` | str | — | Short name (narrow headers); blank = the name. |
| `MINDGRID_BRAND_TAGLINE` | str | — | Optional line under the name. |
| `MINDGRID_BRAND_LOGO_URL` | str | — | Logo image URL or path served by the web app. |
| `MINDGRID_BRAND_PRIMARY_COLOR` | str | `#4f46e5` | Primary UI colour (#rrggbb). |
| `MINDGRID_BRAND_PRIMARY_COLOR_DARK` | str | `#60a5fa` | Primary UI colour in the dark theme (#rrggbb; light enough to read on black). |

## OutboundSettings (`mindgrid.core.netguard`)

Outbound HTTP rules for every call the server makes on someone's behalf (connectors,

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_OUTBOUND_ALLOW_PRIVATE_HOSTS` | comma list | — | Hosts outbound calls may reach although they resolve to a private or loopback address (also allowed over plain http), e.g. an internal service. |

## RuntimeSettings (`mindgrid.core.runtime`)

Process-wide runtime settings.

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_ENV` | Literal['development', 'test', 'production'] | `development` | Deployment environment. |
| `MINDGRID_LOG_LEVEL` | Literal['debug', 'info', 'warning', 'error'] | `info` | Minimum log level. |
| `MINDGRID_LOG_JSON` | bool | `true` | JSON log lines (off = readable console lines). |
| `MINDGRID_DOCS` | bool | `true` | Serve the OpenAPI docs at /docs. |

## DatasetSettings (`mindgrid.datasets.config`)

Dataset limits.

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_DATASET_MAX_BYTES` | int > 0 | `209715200` | Largest dataset file (raw). |
| `MINDGRID_DATASET_KEEP_VERSIONS` | int > 0 | `30` | Versions kept per dataset (older ones go). |

## DatabaseSettings (`mindgrid.db.config`)

Database settings. Two roles: the app connects as a role without BYPASSRLS that owns

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_DATABASE_URL` | secret | — | App connection (postgresql+asyncpg://…), as the non-owner app role. |
| `MINDGRID_MIGRATION_DATABASE_URL` | secret | — | Owner connection used only by migrations; blank = MINDGRID_DATABASE_URL. |
| `MINDGRID_DB_APP_ROLE` | str | `mindgrid_app` | Name of the app role migrations grant table access to. |
| `MINDGRID_DB_POOL_SIZE` | int > 0 | `10` | Connections per process. |
| `MINDGRID_DB_STATEMENT_TIMEOUT_MS` | int > 0 | `15000` | Server-side limit per statement. |

## BodySettings (`mindgrid.interfaces.body_limit`)

Request size caps (OWASP REST: limit request size): uploads get the intake limit, every

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_MAX_BODY_BYTES` | int > 0 | `1048576` | Largest non-upload request body (bytes). |

## RemoteSettings (`mindgrid.interfaces.remote.config`)

Where client profiles and cached tokens live.

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_CONFIG_DIR` | str | — | Client profiles folder (blank = ~/.config/mindgrid). |
| `MINDGRID_CLIENT_CACHE_DIR` | str | — | Token cache folder (blank = ~/.cache/mindgrid). |
| `MINDGRID_PROFILE` | str | `default` | Client profile used by the CLI and the MCP server. |

## WebSettings (`mindgrid.interfaces.web`)

Serve the built web app (web/dist) from the same origin as the API, with security

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_WEB_DIST` | str | — | Built web app folder; blank = API only. |

## EvalSettings (`mindgrid.knowledge.evals.config`)

Recall log retention and eval limits.

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_RECALL_LOG_DAYS` | int ≥ 0 | `90` | Days a question stays in the recall log (0 = do not log questions). |
| `MINDGRID_EVAL_MAX_CASES` | int > 0 | `500` | Most cases in one eval run. |
| `MINDGRID_EVAL_JUDGE_SECONDS` | int > 0 | `120` | Longest wait for the judge on one case. |

## IndexSettings (`mindgrid.knowledge.index.config`)

Indexing tuning (contextual retrieval).

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_INDEX_CONTEXT_SECONDS` | int > 0 | `60` | Longest wait for one chunk's context line. |
| `MINDGRID_INDEX_CONTEXT_MAX_CHARS` | int > 0 | `400` | Longest context line kept per chunk. |
| `MINDGRID_INDEX_CONTEXT_OUTLINE_CHARS` | int > 0 | `2000` | Document outline (its headings) given with each chunk. |
| `MINDGRID_INDEX_CONTEXT_NEIGHBOUR_CHARS` | int > 0 | `600` | Text before and after the chunk given with it. |

## IntakeSettings (`mindgrid.knowledge.intake.config`)

Intake limits and chunking (recursive ~512-token chunks were the strongest default in

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_MAX_UPLOAD_BYTES` | int > 0 | `26214400` | Largest document upload (bytes). |
| `MINDGRID_CHUNK_CHARS` | int > 0 | `2000` | Target chunk size in characters (~512 tokens). |
| `MINDGRID_CHUNK_OVERLAP_CHARS` | int > 0 | `250` | Characters repeated between chunks. |
| `MINDGRID_PDF_MAX_PAGES` | int > 0 | `2000` | Pages read from one PDF at most. |
| `MINDGRID_CSV_ROWS_PER_CHUNK` | int > 0 | `25` | CSV rows per chunk (knowledge mode). |

## RecallSettings (`mindgrid.knowledge.recall.config`)

Recall tuning.

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_RECALL_K` | int > 0 | `8` | Passages returned by default. |
| `MINDGRID_RECALL_MAX_K` | int > 0 | `50` | Most passages per request. |
| `MINDGRID_RECALL_CANDIDATES` | int > 0 | `50` | Candidates each retriever adds before fusion. |
| `MINDGRID_RECALL_RRF_K` | int > 0 | `60` | Reciprocal-rank-fusion constant (higher = flatter). |
| `MINDGRID_RECALL_EF_SEARCH` | int > 0 | `100` | HNSW search breadth (recall vs. speed). |
| `MINDGRID_RECALL_TRIGRAM_THRESHOLD` | float ≥ 0 | `0.3` | Minimum word similarity for the trigram retriever (0-1). |
| `MINDGRID_RECALL_RERANK_CANDIDATES` | int > 0 | `10` | Fused passages the reranker re-scores (at least k). Measured on real documents: 10 matched 16 and 20 in quality at a third of the time. |
| `MINDGRID_RECALL_MIN_RELEVANCE` | float ≥ 0 | `0.005` | Reranker probability below which a passage is dropped as unrelated (measured for bge-reranker-v2-m3: relevant >= 0.011, unrelated <= 0.002). |
| `MINDGRID_RECALL_MAX_VECTOR_DISTANCE` | float ≥ 0 | `0.0` | Without a reranker: a passage without an exact keyword match is dropped beyond this cosine distance. 0 = the value measured for the embedding model (EmbeddingGemma-300m 0.71, Qwen3-Embedding-0.6B 0.6, others 0.6). |
| `MINDGRID_RECALL_REWRITE_SECONDS` | int > 0 | `20` | Longest wait for a query rewrite (setting recall.rewrite); then the original question is searched alone. |
| `MINDGRID_RECALL_MAX_QUERY_CHARS` | int > 0 | `2000` | Longest accepted query. |

## KeySettings (`mindgrid.platform.apikeys.config`)

API key and token lifetimes; the clock skew a signature may have.

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_ACCESS_TOKEN_TTL_S` | int > 0 | `900` | Access token lifetime (seconds). |
| `MINDGRID_REFRESH_TOKEN_TTL_DAYS` | int > 0 | `30` | Refresh token lifetime (days). |
| `MINDGRID_SIGNATURE_SKEW_S` | int > 0 | `300` | Largest allowed clock difference of a signature. |
| `MINDGRID_KEY_MAX_DAYS` | int > 0 | `365` | Longest lifetime of an API key (days). |

## EventSettings (`mindgrid.platform.events.config`)

Event delivery settings.

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_PUBLIC_URL` | str | `http://localhost:8700` | Base URL receivers use to reach this server (links in events, dataschema). |
| `MINDGRID_EVENT_RETRY_SECONDS` | comma list | `('5', '300', '1800', '7200', '18000', '36000', '50400', '72000', '86400')` | Wait before each retry (Standard Webhooks schedule, about 3 days in total). |
| `MINDGRID_EVENT_TIMEOUT_SECONDS` | float > 0 | `15` | Longest wait for a receiver's answer. |
| `MINDGRID_EVENT_MAX_DATA_BYTES` | int > 0 | `20000` | Largest event `data` (thin events link out). |
| `MINDGRID_EVENT_DISABLE_AFTER_DEAD` | int > 0 | `5` | A subscription is switched off after this many dead deliveries in a row. |
| `MINDGRID_EVENT_KEEP_DAYS` | int > 0 | `30` | Days events and their deliveries are kept. |
| `MINDGRID_EVENT_BATCH` | int > 0 | `20` | Deliveries claimed per pass. |
| `MINDGRID_EVENT_EVERY_SECONDS` | float > 0 | `2` | How often the worker looks for due deliveries. |

## SessionSettings (`mindgrid.platform.identity.config`)

Session lifetime (OWASP Session Management: absolute and idle timeouts).

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_SESSION_TTL_HOURS` | int > 0 | `12` | Absolute session lifetime (hours). |
| `MINDGRID_SESSION_IDLE_MINUTES` | int > 0 | `60` | Session ends after this long unused (minutes). |
| `MINDGRID_SESSION_TOUCH_EVERY_S` | int > 0 | `60` | Least time between last-seen writes (s). |

## JobSettings (`mindgrid.platform.jobs.config`)

Worker timing.

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_JOB_LEASE_SECONDS` | int > 0 | `600` | A claimed job not finished within this time is given to another worker. |
| `MINDGRID_JOB_MAX_ATTEMPTS` | int > 0 | `5` | Tries before a job is marked failed. |
| `MINDGRID_JOB_RETRY_BASE_SECONDS` | int > 0 | `30` | First retry delay; doubles each attempt. |
| `MINDGRID_JOB_IDLE_SECONDS` | float > 0 | `2.0` | Worker pause when the queue is empty. |

## SecuritySettings (`mindgrid.platform.security.config`)

Security settings. The secret key signs CSRF tokens and is the root of the keys that

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_SECRET_KEY` | secret | — | Server secret (32+ bytes). Required. |
| `MINDGRID_SIGNIN_LIMIT` | int > 0 | `5` | Sign-in attempts per IP + email per window. |
| `MINDGRID_SIGNIN_IP_LIMIT` | int > 0 | `20` | Sign-in attempts per IP per window. |
| `MINDGRID_SIGNIN_WINDOW_S` | int > 0 | `60` | Sign-in rate-limit window (seconds). |

## EmbeddingSettings (`mindgrid.providers.config`)

Embedding defaults. A project can still choose another embedding space later; vectors

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_EMBEDDING_PROVIDER` | Literal['local', 'gemini', 'hashing'] | `local` | local (on this machine, no key) | gemini (needs the Gemini key) | hashing (tests) |
| `MINDGRID_EMBED_LOCAL_MODEL` | str | `google/embeddinggemma-300m` | fastembed model. Default EmbeddingGemma-300m (multilingual incl. Thai, Gemma terms; measured 6x faster than Qwen/Qwen3-Embedding-0.6B-Q at equal reranked quality; use that one for Apache-2.0). |
| `MINDGRID_EMBED_LOCAL_DIMS` | int ≥ 0 | `0` | Its vector size (0 = the model's known size; must match the model). |
| `MINDGRID_EMBED_THREADS` | int > 0 | `2` | CPU threads for local embedding. |
| `MINDGRID_EMBED_CACHE_DIR` | str | — | Model download folder (blank = ~/.cache/mindgrid/models). |
| `MINDGRID_EMBED_QUERY_TEMPLATE` | str | — | Prompt around a query, with {text} (blank = the model's known format). |
| `MINDGRID_EMBED_DOCUMENT_TEMPLATE` | str | — | Prompt around a document chunk, with {text} (blank = the model's known format). |
| `MINDGRID_EMBED_GEMINI_MODEL` | str | `gemini-embedding-2` | Gemini embedding model. |
| `MINDGRID_EMBED_GEMINI_DIMS` | int > 0 | `1536` | Truncated (MRL) size; pgvector indexes <= 2000. |
| `MINDGRID_EMBED_BATCH` | int > 0 | `16` | Texts per embedding call. |

## LlmSettings (`mindgrid.providers.config`)

Embedding defaults. A project can still choose another embedding space later; vectors

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_LLM_GEMINI_MODEL` | str | `gemini-flash-latest` | Gemini model that writes answers. |
| `MINDGRID_LLM_LOCAL_URL` | str | `http://127.0.0.1:11434` | Ollama server (local mode). |
| `MINDGRID_LLM_LOCAL_MODEL` | str | `qwen3:8b` | Ollama model. |
| `MINDGRID_LLM_LOCAL_CONTEXT_TOKENS` | int > 0 | `16384` | Context window asked of the local model (prompt + answer). Ollama's own default (4096) silently cuts a longer prompt; the passages are fitted to this window. |
| `MINDGRID_LLM_TIMEOUT_SECONDS` | int > 0 | `120` | Longest wait for one answer. |
| `MINDGRID_LLM_TEMPERATURE` | float ≥ 0 | `0.1` | Low = sticks to the passages. |
| `MINDGRID_LLM_MAX_OUTPUT_TOKENS` | int > 0 | `2048` | Longest answer. |

## RerankSettings (`mindgrid.providers.config`)

Embedding defaults. A project can still choose another embedding space later; vectors

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_RERANK_PROVIDER` | Literal['local', 'none'] | `local` | local (cross-encoder on this machine, no key) | none (fused order only) |
| `MINDGRID_RERANK_LOCAL_MODEL` | str | `BAAI/bge-reranker-v2-m3-int8` | fastembed cross-encoder (Apache-2.0, multilingual incl. Thai). |
| `MINDGRID_RERANK_THREADS` | int > 0 | `2` | CPU threads for local reranking. |
| `MINDGRID_RERANK_MAX_CHARS` | int > 0 | `500` | Start of each passage given to the reranker. Measured on real documents: 500 matched 700 and 2000 in quality (350 lost hits); cost grows with length. |

## SynapseSettings (`mindgrid.synapse.config`)

Synapse limits and where sources may live.

| Variable | Type | Default | Description |
|---|---|---|---|
| `MINDGRID_SYNAPSE_ALLOWED_ROOTS` | comma list | — | Folders a source repository may be in (absolute paths; empty = none allowed). |
| `MINDGRID_SYNAPSE_MAX_FILE_BYTES` | int > 0 | `200000` | Largest file read from a source. |
| `MINDGRID_SYNAPSE_MAX_ITEMS` | int > 0 | `200` | Most items in one proposal. |
| `MINDGRID_SYNAPSE_GIT_TIMEOUT` | int > 0 | `30` | Longest wait for one git command. |
