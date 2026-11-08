# The console image: the built Vue app and the FastAPI process that serves it and the JSON API.
# One image, on library's pattern (docs/decisions.md D7). amd64 only.
#
# Runs as uid 10001 on a read-only root filesystem: nothing here writes outside /tmp and the audit
# log's directory, /var/lib/nanoclaw-console/audit (PYTHONDONTWRITEBYTECODE, no cache). The
# deployment mounts a named volume there; Docker fills a new named volume from the image's
# directory, owner and mode included, so the image ships that directory empty, 10001's and 0700.

# --- Stage 1: build the web app (web/ → /web/dist) ---
FROM node:22-alpine AS web
WORKDIR /web
# npm 11: npm 10.9's resolver crashes on this dependency tree (tracker, docs/development.md).
RUN npm install -g npm@11
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
# Type-checks (vue-tsc) and builds (vite) into dist/. tokens.css is committed, so no Python here.
RUN npm run build

# --- Stage 2: install the API's locked dependencies with uv ---
FROM ghcr.io/astral-sh/uv:0.13.0 AS uv

FROM python:3.13-slim AS build
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /build
COPY api/pyproject.toml api/uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project -o requirements.txt \
 && uv pip install --target /app --python-version 3.13 --only-binary :all: -r requirements.txt
COPY api/src/nanoclaw_console /app/nanoclaw_console
RUN install -d -m 0700 /audit

# --- Runtime: only COPY steps on top of the slim Python image ---
FROM python:3.13-slim
ENV PYTHONPATH=/app PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 STATIC_DIR=/app/static
COPY --from=build /app /app
COPY --from=web /web/dist /app/static
COPY --from=build --chown=10001:10001 --chmod=0700 /audit /var/lib/nanoclaw-console/audit
# The commit's revision label is added by the publish workflow (docker.yml), not here.
LABEL org.opencontainers.image.source="https://github.com/johnmathews/nanoclaw-console"
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]
CMD ["python", "-m", "uvicorn", "--factory", "nanoclaw_console.app:create_app_from_env", \
     "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
