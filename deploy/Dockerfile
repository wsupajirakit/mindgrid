# syntax=docker/dockerfile:1.7
# One image for the API, the worker and migrations (different commands). Build from the
# repository root: docker build -f deploy/Dockerfile -t mindgrid:<version> .
# Base images are pinned by digest; move them forward on purpose, with the lock files.

FROM node:26.8.1-slim@sha256:c0753125a3789977aefe869cbebccf70e3cfd7ea84ca48547458f02e4f1d7146 AS web
WORKDIR /src/web
COPY web/package.json web/package-lock.json web/.npmrc ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY web/ ./
RUN npm run gen:i18n && npm run build

FROM ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff AS uv

FROM python:3.14.5-slim@sha256:c845af9399020c7e562969a13689e929074a10fd057acd1b1fad06a2fb068e97 AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
# git: Synapse reads source repositories (read-only); ca-certificates: outbound https.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 --shell /usr/sbin/nologin app \
 && mkdir -p /data/models && chown app:app /data/models
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app/backend
# Dependencies first (cached while only the code changes), then the code.
COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/packs ./packs
RUN uv sync --frozen --no-dev --no-install-workspace
COPY backend/src ./src
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./
RUN uv sync --frozen --no-dev && rm /usr/local/bin/uv
COPY --from=web /src/web/dist /app/web/dist
ENV PATH=/app/backend/.venv/bin:$PATH \
    MINDGRID_ENV=production MINDGRID_LOG_JSON=true \
    MINDGRID_WEB_DIST=/app/web/dist MINDGRID_EMBED_CACHE_DIR=/data/models
USER app
EXPOSE 8700
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8700/v1/health', timeout=3).status == 200 else 1)"]
CMD ["uvicorn", "--factory", "mindgrid.app:create_app", "--host", "0.0.0.0", "--port", "8700", \
     "--no-server-header", "--proxy-headers", "--forwarded-allow-ips", "*"]
