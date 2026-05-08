"""Aggregator service entrypoint — Slice 1+.

Consumes `trial_results` Redis Stream, scores trials, signs attestations,
persists results to Postgres.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

from . import __version__
from .pipeline import run_pipeline

log = structlog.get_logger()

heartbeats = Counter("aggregator_heartbeats_total", "Heartbeats since process start")

REDIS_URL = os.environ.get("POLYEVAL_REDIS_URL", "redis://redis:6379/0")
DB_URL = os.environ.get("POLYEVAL_DB_URL", "postgresql://polyeval:polyeval@postgres:5432/polyeval")
HEARTBEAT_KEY = "polyeval:aggregator:heartbeat"
HEARTBEAT_INTERVAL_S = 5.0


async def _heartbeat_loop(client: aioredis.Redis) -> None:  # type: ignore[type-arg]
    while True:
        try:
            heartbeats.inc()
            await client.set(HEARTBEAT_KEY, str(int(asyncio.get_event_loop().time())), ex=30)
        except Exception as err:
            log.warning("aggregator.redis.unreachable", error=str(err))
        await asyncio.sleep(HEARTBEAT_INTERVAL_S)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    client: aioredis.Redis = aioredis.from_url(REDIS_URL, decode_responses=True)  # type: ignore[type-arg]
    app.state.redis = client
    heartbeat_task = asyncio.create_task(_heartbeat_loop(client))
    pipeline_task = asyncio.create_task(run_pipeline(REDIS_URL, DB_URL))
    log.info("aggregator.startup", version=__version__, redis_url=REDIS_URL)
    try:
        yield
    finally:
        heartbeat_task.cancel()
        pipeline_task.cancel()
        for task in (heartbeat_task, pipeline_task):
            try:
                await task
            except asyncio.CancelledError:
                pass
        await client.aclose()
        log.info("aggregator.shutdown")


def create_app() -> FastAPI:
    app = FastAPI(title="PolyEval Aggregator", version=__version__, lifespan=lifespan)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "polyeval-aggregator", "version": __version__}

    @app.get("/readyz")
    async def readyz() -> JSONResponse:
        client: redis.Redis = app.state.redis
        try:
            ok = await client.ping()
        except redis.RedisError:
            ok = False
        return JSONResponse(
            status_code=200 if ok else 503,
            content={"status": "ok" if ok else "degraded", "checks": {"redis": "ok" if ok else "fail"}},
        )

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> PlainTextResponse:
        return PlainTextResponse(
            content=generate_latest().decode("utf-8"),
            media_type=CONTENT_TYPE_LATEST,
        )

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run(
        "polyeval_aggregator.main:app",
        host="0.0.0.0",  # noqa: S104 — bound inside container
        port=8002,
        log_config=None,
    )
