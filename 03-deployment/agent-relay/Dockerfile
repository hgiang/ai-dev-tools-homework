# syntax=docker/dockerfile:1

# ---- build stage -------------------------------------------------------------
# Resolve dependencies with uv into a self-contained .venv.  Nothing from this
# stage other than that .venv reaches the final image, so uv itself, the build
# cache and the lockfile stay out of the shipped layers.
FROM python:3.11-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.9.6 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Copy only the dependency manifests first: this layer is cached and re-used on
# every rebuild where dependencies did not change, so editing a .py file does
# not re-resolve the whole dependency tree.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project


# ---- runtime stage -----------------------------------------------------------
FROM python:3.11-slim AS runtime

# Run as an unprivileged user.  A container that only serves HTTP has no reason
# to be root, and Kubernetes (Q5) can then enforce runAsNonRoot.
RUN useradd --create-home --uid 10001 relay

WORKDIR /app

COPY --from=build --chown=relay:relay /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Application sources.  Listed explicitly rather than `COPY . .` so that local
# artefacts (.venv, *.db, *-credentials.json, .git) can never leak into the
# image even if .dockerignore is edited later.
COPY --chown=relay:relay \
    main.py worker.py storage.py database.py schemas.py errors.py dashboard.py \
    dashboard.html SPEC.md \
    ./

# SQLite default lives here so a volume can be mounted on /data.  Q4 overrides
# RELAY_DATABASE_URL with a PostgreSQL URL and this becomes unused.
RUN mkdir -p /data && chown relay:relay /data
ENV RELAY_DATABASE_URL="sqlite:////data/agent-relay.db"

USER relay
EXPOSE 8000

# 0.0.0.0, not 127.0.0.1: the server must accept connections from outside the
# container's own network namespace, otherwise -p publishes a port nothing listens on.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
