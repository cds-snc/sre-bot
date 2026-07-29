# ── builder ──────────────────────────────────────────────────────────────────
FROM python:3.14-slim@sha256:1697e8e8d39bf168e177ac6b5fdab6df86d81cfc24dae17dfb96cfc3ef76b4dd AS builder

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
FROM python:3.14-slim@sha256:1697e8e8d39bf168e177ac6b5fdab6df86d81cfc24dae17dfb96cfc3ef76b4dd

WORKDIR /app

# Install AWS CLI via the official version-pinned installer with GPG verification.
# Debian bookworm does not package awscli; AWS explicitly recommends this path
# for reproducible, integrity-checked installs.
ARG AWSCLI_VERSION=2.36.10
COPY aws-cli-pubkey.asc /tmp/aws-cli-pubkey.asc
RUN apt-get update \
   && apt-get install -y --no-install-recommends curl unzip gnupg \
   && curl -fsSL -o /tmp/awscliv2.zip \
   "https://awscli.amazonaws.com/awscli-exe-linux-x86_64-${AWSCLI_VERSION}.zip" \
   && curl -fsSL -o /tmp/awscliv2.sig \
   "https://awscli.amazonaws.com/awscli-exe-linux-x86_64-${AWSCLI_VERSION}.zip.sig" \
   && gpg --import /tmp/aws-cli-pubkey.asc \
   && gpg --verify /tmp/awscliv2.sig /tmp/awscliv2.zip \
   && unzip /tmp/awscliv2.zip -d /tmp/awscli \
   && /tmp/awscli/aws/install \
   && rm -rf /tmp/awscliv2.zip /tmp/awscliv2.sig /tmp/awscli /tmp/aws-cli-pubkey.asc \
   && apt-get purge -y --auto-remove curl unzip gnupg \
   && rm -rf /var/lib/apt/lists/*

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

COPY app/bin/entry.sh /app/entry.sh

# Run as a non-root, unprivileged user (OWASP Docker Security Cheat Sheet Rule #2).
# entry.sh writes ".env" into WORKDIR at container start, so the app directory
# (including the venv and geodb assets copied above) must be owned by that user.
RUN groupadd --system --gid 1000 appuser \
   && useradd --system --uid 1000 --gid appuser --home-dir /app --shell /usr/sbin/nologin appuser \
   && chown -R appuser:appuser /app

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
   CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

ENTRYPOINT [ "/app/entry.sh" ]