# syntax=docker/dockerfile:1.7
# --- build stage: installs only production deps ---
FROM python:3.12-slim AS build

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src

RUN pip install --upgrade pip && pip install -e .

# --- dev stage: adds dev extras + reload ---
FROM build AS dev

ARG INSTALL_DEV=true
RUN if [ "$INSTALL_DEV" = "true" ]; then pip install -e .[dev]; fi

# Non-root user.
RUN useradd --create-home --shell /usr/sbin/nologin polyeval \
    && chown -R polyeval:polyeval /app
USER polyeval

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "polyeval_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# --- prod stage: no dev deps, no reload ---
FROM build AS prod

RUN useradd --create-home --shell /usr/sbin/nologin polyeval \
    && chown -R polyeval:polyeval /app
USER polyeval

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "polyeval_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
