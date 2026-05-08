# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

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
RUN pip install --upgrade pip \
    && pip install -e .

RUN useradd --create-home --shell /usr/sbin/nologin polyeval \
    && chown -R polyeval:polyeval /app
USER polyeval

EXPOSE 8002

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -fsS http://localhost:8002/healthz || exit 1

CMD ["uvicorn", "polyeval_aggregator.main:app", "--host", "0.0.0.0", "--port", "8002"]
