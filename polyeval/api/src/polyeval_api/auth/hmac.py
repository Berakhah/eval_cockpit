"""HMAC-SHA256 request authentication — spec §12.1.

All authenticated endpoints depend on `verify_hmac` which:
1. Checks required headers (Signature, Timestamp, Nonce, Tenant).
2. Rejects if |now - timestamp| > 300 s.
3. Stores nonce in Redis for 600 s (replay protection via SETNX).
4. Verifies HMAC-SHA256 over raw body using POLYEVAL_HMAC_SECRET.
5. Returns tenant_id stashed on request.state.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from datetime import UTC, datetime

import redis.asyncio as aioredis
import structlog
from fastapi import Depends, Header, HTTPException, Request, status

from ..settings import Settings, get_settings

log = structlog.get_logger()

_TIMESTAMP_TOLERANCE_S = 300
_NONCE_TTL_S = 600
_HMAC_PREFIX = "hmac-sha256:"


def _constant_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def _compute_hmac(secret: str, body: bytes) -> str:
    mac = hmac.new(secret.encode(), body, hashlib.sha256)
    return _HMAC_PREFIX + mac.hexdigest()


async def _get_redis(settings: Settings = Depends(get_settings)) -> aioredis.Redis:  # type: ignore[type-arg]
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def verify_hmac(
    request: Request,
    x_polyeval_signature: str = Header(..., alias="X-Polyeval-Signature"),
    x_polyeval_timestamp: str = Header(..., alias="X-Polyeval-Timestamp"),
    x_polyeval_nonce: str = Header(..., alias="X-Polyeval-Nonce"),
    x_polyeval_tenant: str = Header(..., alias="X-Polyeval-Tenant"),
    settings: Settings = Depends(get_settings),
) -> str:
    """FastAPI dependency. Returns tenant_id on success; raises 401 on failure."""
    # 1. Validate timestamp window.
    try:
        ts = datetime.fromisoformat(x_polyeval_timestamp.replace("Z", "+00:00"))
        age_s = abs((datetime.now(UTC) - ts).total_seconds())
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_timestamp")

    if age_s > _TIMESTAMP_TOLERANCE_S:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="clock_skew")

    # 2. Replay protection via Redis nonce.
    redis: aioredis.Redis = aioredis.from_url(settings.redis_url, decode_responses=True)  # type: ignore[type-arg]
    nonce_key = f"poly:nonce:{x_polyeval_nonce}"
    try:
        stored = await redis.set(nonce_key, "1", ex=_NONCE_TTL_S, nx=True)
    except Exception:
        # Fail closed: if Redis is down we cannot verify nonces → 503.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="nonce_store_unavailable")
    finally:
        await redis.aclose()

    if not stored:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="replay")

    # 3. Verify HMAC over raw body.
    if not settings.hmac_secret:
        # Dev mode with no secret configured — skip verification for local dev.
        if settings.environment == "prod":
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="hmac_not_configured")
    else:
        body = await request.body()
        expected = _compute_hmac(settings.hmac_secret, body)
        if not _constant_compare(expected, x_polyeval_signature):
            log.warning("auth.hmac_fail", tenant=x_polyeval_tenant)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_signature")

    request.state.tenant_id = x_polyeval_tenant
    return x_polyeval_tenant
