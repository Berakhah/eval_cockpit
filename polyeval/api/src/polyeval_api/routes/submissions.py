"""Submission routes — spec §6: POST, GET, attestation.

POST /v1/submissions  — HMAC-verified, cache-checked, enqueued
GET  /v1/submissions/{id}  — poll status
GET  /v1/submissions/{id}/attestation  — download signed attestation
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from opentelemetry import trace

from ..auth import verify_hmac
from ..cache import build_cache_key, cache_get, cache_set
from ..db import tenant_connection
from ..metrics import cache_hits_total, cache_misses_total, submissions_total
from ..schemas import (
    Attestation,
    ScoredResult,
    SubmissionCreate,
    SubmissionListItem,
    SubmissionResponse,
    SubmitResponse,
)
from ..settings import Settings, get_settings

log = structlog.get_logger()
tracer = trace.get_tracer("polyeval.api")
router = APIRouter(prefix="/v1/submissions", tags=["submissions"])

# Redis stream where scheduler reads work.
_EVAL_QUEUE = "eval:queue"


def _sha256_bytes(data: str) -> bytes:
    return hashlib.sha256(data.encode()).digest()


def _serialize_test_suite(ts: Any) -> str:
    return json.dumps(ts.model_dump(), sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------------------
# GET /v1/submissions  — list recent submissions for this tenant
# ---------------------------------------------------------------------------
@router.get(
    "",
    response_model=list[SubmissionListItem],
    summary="List recent submissions for tenant (spec §6)",
)
async def list_submissions(
    tenant_id: str = Depends(verify_hmac),
    limit: int = 100,
) -> list[SubmissionListItem]:
    with tracer.start_as_current_span("submission.list") as span:
        span.set_attribute("polyeval.tenant", tenant_id)
        async with tenant_connection(tenant_id) as conn:
            rows = await conn.fetch(
                """
                SELECT s.id, s.tenant_id, s.model_id, s.language,
                       s.status, s.created_at,
                       r.trials_total,
                       r.correctness_score,
                       r.perf_normalized,
                       r.reliability_score
                FROM submissions s
                LEFT JOIN results r ON r.id = s.id
                WHERE s.tenant_id = current_setting('app.tenant_id')
                ORDER BY s.created_at DESC
                LIMIT $1
                """,
                limit,
            )
        return [
            SubmissionListItem(
                id=row["id"],
                tenant_id=row["tenant_id"],
                model_id=row["model_id"],
                language=row["language"],
                status=row["status"],
                trials_total=row["trials_total"],
                correctness=float(row["correctness_score"]) if row["correctness_score"] is not None else None,
                perf_normalized=float(row["perf_normalized"]) if row["perf_normalized"] is not None else None,
                reliability=float(row["reliability_score"]) if row["reliability_score"] is not None else None,
                created_at=row["created_at"],
            )
            for row in rows
        ]


# ---------------------------------------------------------------------------
# POST /v1/submissions
# ---------------------------------------------------------------------------
@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=SubmitResponse,
    summary="Submit code for evaluation (spec §6)",
)
async def create_submission(
    request: Request,
    body: SubmissionCreate,
    tenant_id: str = Depends(verify_hmac),
    settings: Settings = Depends(get_settings),
) -> SubmitResponse:
    with tracer.start_as_current_span("submission.create") as span:
        span.set_attribute("polyeval.tenant", tenant_id)
        span.set_attribute("polyeval.lang", body.language)
        span.set_attribute("polyeval.model_id", body.model_id)

        redis: aioredis.Redis = aioredis.from_url(settings.redis_url, decode_responses=True)  # type: ignore[type-arg]
        try:
            # Cache lookup (spec §5.2).
            runner_digest = "sha256:dev"  # replaced by scheduler in prod flow
            cache_key = build_cache_key(
                tenant_id=tenant_id,
                model_id=body.model_id,
                language=body.language,
                prompt=body.prompt,
                test_suite_serialized=_serialize_test_suite(body.test_suite),
                runner_image_digest=runner_digest,
            )
            with tracer.start_as_current_span("cache.lookup") as cache_span:
                cached = await cache_get(redis, cache_key)
                cache_span.set_attribute("cache.hit", cached is not None)

            if cached is not None:
                log.info("submission.cache_hit", tenant=tenant_id)
                cache_hits_total.inc()
                return SubmitResponse(id=UUID(cached["id"]), replay=True)
            cache_misses_total.inc()

            # Insert into DB.
            sub_id = uuid.uuid4()
            prompt_hash = _sha256_bytes(body.prompt)
            test_suite_hash = _sha256_bytes(_serialize_test_suite(body.test_suite))
            code_bytes = body.code.encode()

            async with tenant_connection(tenant_id) as conn:
                with tracer.start_as_current_span("db.insert_submission"):
                    await conn.execute(
                        """
                        INSERT INTO submissions
                          (id, tenant_id, model_id, language,
                           prompt_hash, test_suite_hash, code,
                           status, version, created_at, updated_at)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,'queued',1,now(),now())
                        """,
                        sub_id, tenant_id, body.model_id, body.language,
                        prompt_hash, test_suite_hash, code_bytes,
                    )

            # Enqueue for scheduler.
            payload = json.dumps({
                "submission_id": str(sub_id),
                "language": body.language,
                "priority": 1,
                "enqueued_at": datetime.now(UTC).isoformat(),
                "trials": body.trials,
                "timeout_seconds": body.timeout_seconds,
                "memory_limit_mb": body.memory_limit_mb,
                "determinism_seed": body.determinism_seed,
                "test_suite": body.test_suite.model_dump(),
                "code": body.code,
            })
            with tracer.start_as_current_span("queue.xadd") as q_span:
                q_span.set_attribute("stream", _EVAL_QUEUE)
                await redis.xadd(_EVAL_QUEUE, {"data": payload})

            submissions_total.labels(language=body.language).inc()
            log.info("submission.enqueued", id=str(sub_id), tenant=tenant_id)
            span.set_attribute("polyeval.submission_id", str(sub_id))
            return SubmitResponse(id=sub_id, replay=False)
        finally:
            await redis.aclose()


# ---------------------------------------------------------------------------
# GET /v1/submissions/{id}
# ---------------------------------------------------------------------------
@router.get(
    "/{submission_id}",
    response_model=SubmissionResponse,
    summary="Poll submission status (spec §6)",
)
async def get_submission(
    submission_id: UUID,
    tenant_id: str = Depends(verify_hmac),
) -> SubmissionResponse:
    with tracer.start_as_current_span("submission.get") as span:
        span.set_attribute("polyeval.tenant", tenant_id)
        span.set_attribute("polyeval.submission_id", str(submission_id))

        async with tenant_connection(tenant_id) as conn:
            row = await conn.fetchrow(
                """
                SELECT s.id, s.tenant_id, s.model_id, s.language,
                       s.status, s.version, s.created_at, s.updated_at,
                       r.correctness_score, r.correctness_ci_lo, r.correctness_ci_hi,
                       r.reliability_score, r.flaky,
                       r.perf_normalized, r.perf_ci_lo, r.perf_ci_hi,
                       r.trials_total, r.trials_passed,
                       r.wall_time_ms_p50, r.wall_time_ms_p95,
                       r.mem_peak_mb, r.attestation_pubkey_id,
                       r.raw_trials, r.scored_at
                FROM submissions s
                LEFT JOIN results r ON r.id = s.id
                WHERE s.id = $1
                """,
                submission_id,
            )

        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")

        result: ScoredResult | None = None
        if row["status"] == "scored" and row["correctness_score"] is not None:
            from ..schemas.submission import CI, Trial
            raw_trials = json.loads(row["raw_trials"] or "[]")
            result = ScoredResult(
                correctness=float(row["correctness_score"]),
                correctness_ci=CI(lo=float(row["correctness_ci_lo"]), hi=float(row["correctness_ci_hi"])),
                reliability=float(row["reliability_score"]),
                flaky=bool(row["flaky"]),
                perf_normalized=float(row["perf_normalized"]) if row["perf_normalized"] else None,
                perf_ci=CI(lo=float(row["perf_ci_lo"]), hi=float(row["perf_ci_hi"])) if row["perf_ci_lo"] else None,
                trials_total=row["trials_total"],
                trials_passed=row["trials_passed"],
                wall_time_ms_p50=row["wall_time_ms_p50"],
                wall_time_ms_p95=row["wall_time_ms_p95"],
                mem_peak_mb=row["mem_peak_mb"],
                attestation_pubkey_id=row["attestation_pubkey_id"],
                scored_at=row["scored_at"],
                raw_trials=[Trial(**t) for t in raw_trials],
            )

        return SubmissionResponse(
            id=row["id"],
            tenant_id=row["tenant_id"],
            model_id=row["model_id"],
            language=row["language"],
            status=row["status"],
            version=row["version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            result=result,
        )


# ---------------------------------------------------------------------------
# GET /v1/submissions/{id}/attestation
# ---------------------------------------------------------------------------
@router.get(
    "/{submission_id}/attestation",
    summary="Download signed Ed25519 attestation (spec §9)",
)
async def get_attestation(
    submission_id: UUID,
    tenant_id: str = Depends(verify_hmac),
) -> dict[str, Any]:
    async with tenant_connection(tenant_id) as conn:
        row = await conn.fetchrow(
            """
            SELECT s.model_id, s.language, s.prompt_hash, s.test_suite_hash,
                   s.status, s.tenant_id,
                   r.correctness_score, r.correctness_ci_lo, r.correctness_ci_hi,
                   r.reliability_score, r.perf_normalized, r.perf_ci_lo, r.perf_ci_hi,
                   r.trials_total, r.attestation_pubkey_id, r.attestation_sig, r.scored_at
            FROM submissions s
            LEFT JOIN results r ON r.id = s.id
            WHERE s.id = $1
            """,
            submission_id,
        )

    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")
    if row["status"] != "scored":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="not_scored_yet")
    if row["attestation_sig"] is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no_attestation")

    import base64

    # Reconstruct the attestation JSON (canonical form built by aggregator).
    attestation: dict[str, Any] = {
        "version": "1.0",
        "submission_id": str(submission_id),
        "tenant_id": row["tenant_id"],
        "model_id": row["model_id"],
        "language": row["language"],
        "prompt_hash": row["prompt_hash"].hex(),
        "test_suite_hash": row["test_suite_hash"].hex(),
        "scores": {
            "correctness": float(row["correctness_score"]),
            "correctness_ci": [float(row["correctness_ci_lo"]), float(row["correctness_ci_hi"])],
            "reliability": float(row["reliability_score"]),
            "perf_normalized": float(row["perf_normalized"]) if row["perf_normalized"] else None,
            "perf_ci": [float(row["perf_ci_lo"]), float(row["perf_ci_hi"])] if row["perf_ci_lo"] else None,
        },
        "trials": row["trials_total"],
        "scored_at": row["scored_at"].isoformat(),
        "pubkey_id": row["attestation_pubkey_id"],
        "signature_algorithm": "Ed25519",
        "signature": base64.b64encode(bytes(row["attestation_sig"])).decode(),
    }
    return attestation
