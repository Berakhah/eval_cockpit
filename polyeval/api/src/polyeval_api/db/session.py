"""Async Postgres connection pool and per-request session with RLS tenant scoping."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg
import structlog

from ..settings import Settings

log = structlog.get_logger()

_pool: asyncpg.Pool | None = None  # type: ignore[type-arg]


async def init_pool(settings: Settings) -> None:
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=settings.db_url.replace("+asyncpg", ""),
        min_size=2,
        max_size=10,
        server_settings={"jit": "off"},
    )
    log.info("db.pool_created")


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:  # type: ignore[type-arg]
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call init_pool() first")
    return _pool


@asynccontextmanager
async def tenant_connection(tenant_id: str) -> AsyncIterator[asyncpg.Connection]:  # type: ignore[type-arg]
    """Acquire a connection with RLS tenant scoped for the duration.

    SET LOCAL only takes effect inside a transaction — wrapping in conn.transaction()
    ensures the variable resets when the context exits, preventing pool contamination.
    """
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute("SET LOCAL app.tenant_id = $1", tenant_id)
            yield conn


async def get_db() -> AsyncIterator[asyncpg.Connection]:  # type: ignore[type-arg]
    """FastAPI dependency: yield a plain connection from the pool."""
    async with get_pool().acquire() as conn:
        yield conn
