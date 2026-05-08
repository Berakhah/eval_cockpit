"""Content-addressed Redis cache for submission results — spec §5.2.

Cache key: poly:cache:v1:{tenant_id}:{model_id}:{lang}:sha256(prompt||tests||runner_digest)
TTL: POLYEVAL_CACHE_TTL_DAYS * 86400 seconds (default 30 days).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import redis.asyncio as aioredis
import structlog

from ..settings import Settings

log = structlog.get_logger()

_PREFIX = "poly:cache:v1"


def _sha256_hex(*parts: str | bytes) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode() if isinstance(p, str) else p)
    return h.hexdigest()


def build_cache_key(
    tenant_id: str,
    model_id: str,
    language: str,
    prompt: str,
    test_suite_serialized: str,
    runner_image_digest: str,
) -> str:
    """Deterministic cache key per spec §5.2. Tenant-scoped from day 1."""
    content_hash = _sha256_hex(prompt, test_suite_serialized, runner_image_digest)
    return f"{_PREFIX}:{tenant_id}:{model_id}:{language}:{content_hash}"


async def cache_get(
    redis: aioredis.Redis,  # type: ignore[type-arg]
    key: str,
) -> dict[str, Any] | None:
    raw = await redis.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        log.warning("cache.decode_error", key=key)
        return None


async def cache_set(
    redis: aioredis.Redis,  # type: ignore[type-arg]
    key: str,
    value: dict[str, Any],
    ttl_days: int,
) -> None:
    await redis.setex(key, ttl_days * 86400, json.dumps(value))
