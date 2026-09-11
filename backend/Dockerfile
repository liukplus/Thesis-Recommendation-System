# ============================================
# Backend — Python FastAPI + cat-sdk
# ============================================
# NOTE: the build context is the REPO ROOT, not ./backend.
# `backend/` is a uv *workspace member*; the lockfile (uv.lock) and the
# workspace manifest live at the repo root, so both must be in the context
# for reproducible `uv sync --frozen` builds.
#
# Build:
#   docker build -t thesis-recsys-backend -f backend/Dockerfile .
#
# Run (with CAT server):
#   docker compose --profile cat up backend
# ============================================

FROM python:3.11-slim AS builder

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy workspace manifests + lockfile first — this layer is cached
# unless dependencies change.
COPY pyproject.toml uv.lock .python-version ./
COPY backend/pyproject.toml backend/pyproject.toml

# Resolve and install dependencies only (not the app package itself).
# --frozen: fail rather than silently re-resolving if uv.lock is stale.
RUN uv sync --frozen --no-install-project --no-dev --no-cache --package app

# Copy source code, then install the app package itself
COPY backend/src backend/src
RUN uv sync --frozen --no-dev --no-cache --package app


# --- Runtime stage ---
FROM python:3.11-slim

# Runtime shared libs for cat-sdk (loads its native client through cffi)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi8 \
    && rm -rf /var/lib/apt/lists/*

# CAT expects these paths:
#   /data/appdatas/cat/client.xml  — server routing config (mounted by compose)
#   /data/applogs/cat/             — client-side logs
RUN mkdir -p /data/appdatas/cat /data/applogs/cat

WORKDIR /app

# The venv contains an *editable* install of the `app` package pointing at
# /app/backend/src, so that path must match the builder stage exactly.
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/backend/src /app/backend/src

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
