# ── builder ──────────────────────────────────────────────────────────────────
FROM python:3.14-slim@sha256:cea0e6040540fb2b965b6e7fb5ffa00871e632eef63719f0ea54bca189ce14a6 AS builder

WORKDIR /app

RUN pip install --no-cache-dir uv

# COPY without glob: missing uv.lock fails the build (AC#1)
COPY app/pyproject.toml app/uv.lock ./

# Install dependencies only (cacheable layer)
RUN uv sync --locked --no-dev --no-install-project

# Copy source and install the project itself (non-editable, so entry-point
# metadata is written to .venv — required by pluggy load_setuptools_entrypoints)
COPY app/ .
RUN uv sync --locked --no-dev --no-editable

# ── runtime ───────────────────────────────────────────────────────────────────
FROM python:3.14-slim@sha256:cea0e6040540fb2b965b6e7fb5ffa00871e632eef63719f0ea54bca189ce14a6

WORKDIR /app

# Copy venv (with installed project + entry-point metadata) and source
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"

# Set build variables
ARG git_sha
ENV GIT_SHA=$git_sha

LABEL org.opencontainers.image.title="sre-bot" \
   org.opencontainers.image.source="https://github.com/cds-snc/sre-bot" \
   org.opencontainers.image.revision="${git_sha}"

COPY GeoLite2-City.tar.gz /app/geodb/GeoLite2-City.tar.gz

RUN tar -xzvf /app/geodb/GeoLite2-City.tar.gz -C /app/geodb \
   && cp /app/geodb/GeoLite2-City_*/GeoLite2-City.mmdb /app/geodb/GeoLite2-City.mmdb \
   && rm -rf /app/geodb/GeoLite2-City_* \
   && rm /app/geodb/GeoLite2-City.tar.gz

# Run as a non-root, unprivileged user (OWASP Docker Security Cheat Sheet Rule #2),
# owning the app directory (the venv and geodb assets copied above).
RUN groupadd --system --gid 1000 appuser \
   && useradd --system --uid 1000 --gid appuser --home-dir /app --shell /usr/sbin/nologin appuser \
   && chown -R appuser:appuser /app

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
   CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

# Configuration comes from the configuration files and the task definition's environment and
# secrets (decisions/configuration.md); nothing is fetched at start.
ENTRYPOINT [ "uvicorn", "--factory", "main:create_app", "--host=0.0.0.0" ]