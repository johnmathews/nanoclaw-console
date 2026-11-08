# The broker image: the only process that opens NanoClaw's ncl.sock (docs/architecture.md §2).
# Standard library only at runtime; any locked dependency (none today) is installed with uv.
# Runs as uid 1000, NanoClaw's own user, because ncl.sock is that user's. It serves a Unix socket
# and publishes no port. Pinned to a SHA on the host and upgraded deliberately, never by WUD.

FROM ghcr.io/astral-sh/uv:0.13.0 AS uv

FROM python:3.13-slim AS build
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /build
COPY pyproject.toml uv.lock ./
# An export with no dependencies is only its comment header; install only when it names packages.
RUN uv export --frozen --no-dev --no-emit-project -o requirements.txt \
 && mkdir -p /app \
 && if grep -qv '^#' requirements.txt; then \
      uv pip install --target /app --python-version 3.13 --only-binary :all: -r requirements.txt; \
    fi
COPY src/nanoclaw_broker /app/nanoclaw_broker

FROM python:3.13-slim
ENV PYTHONPATH=/app PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=build /app /app
LABEL org.opencontainers.image.source="https://github.com/johnmathews/nanoclaw-console"
USER 1000:1000
ENTRYPOINT ["python", "-m", "nanoclaw_broker"]
