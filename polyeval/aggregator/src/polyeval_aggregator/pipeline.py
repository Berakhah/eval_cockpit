"""Aggregator pipeline — spec §3.2 steps 11-12.

Reads trial bundles from Redis stream `trial_results`,
scores them, signs an attestation, persists results to Postgres.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import numpy as np
import redis.asyncio as aioredis
import structlog

from .attestation.sign import load_key, sign_attestation
from .metrics import (
    correctness_score as metric_correctness_score,
    non_deterministic_total,
    sandbox_violations_total,
    scored_total,
    scoring_duration_seconds,
)
from .score.correctness import score_correctness
from .score.perf import score_perf
from .score.reliability import score_reliability
from .stats.trim import trim_outliers

log = structlog.get_logger()

_TRIAL_RESULTS_STREAM = "trial_results"
_CONSUMER_GROUP = "aggregators"
_CONSUMER_NAME = f"aggregator-{os.getpid()}"
_WARMUP_TRIALS = 2  # first N trials discarded per spec §7.3


async def _ensure_consumer_group(redis: aioredis.Redis) -> None:  # type: ignore[type-arg]
    try:
        await redis.xgroup_create(_TRIAL_RESULTS_STREAM, _CONSUMER_GROUP, id="0", mkstream=True)
    except Exception:
        pass  # already exists


async def run_pipeline(redis_url: str, db_dsn: str, privkey_path: Path | None = None) -> None:
    """Main aggregator loop. Call from main.py lifespan."""
    load_key(privkey_path)

    redis: aioredis.Redis = aioredis.from_url(redis_url, decode_responses=True)  # type: ignore[type-arg]
    # asyncpg requires plain postgresql:// — strip SQLAlchemy dialect prefix if present.
    pg_dsn = db_dsn.replace("+asyncpg", "").replace("+psycopg2", "")
    pool = await asyncpg.create_pool(dsn=pg_dsn, min_size=2, max_size=5)
    await _ensure_consumer_group(redis)

    log.info("pipeline.started")
    while True:
        try:
            messages = await redis.xreadgroup(
                groupname=_CONSUMER_GROUP,
                consumername=_CONSUMER_NAME,
                streams={_TRIAL_RESULTS_STREAM: ">"},
                count=1,
                block=2000,
            )
        except Exception as exc:
            log.error("pipeline.xreadgroup_error", error=str(exc))
            continue

        if not messages:
            continue

        for _stream, entries in messages:
            for msg_id, fields in entries:
                try:
                    await _process_entry(fields, pool)
                    await redis.xack(_TRIAL_RESULTS_STREAM, _CONSUMER_GROUP, msg_id)
                except Exception as exc:
                    log.error("pipeline.process_error", msg_id=msg_id, error=str(exc))


async def _process_entry(fields: dict[str, str], pool: asyncpg.Pool) -> None:  # type: ignore[type-arg]
    t_entry_start = datetime.now(UTC).timestamp()
    data = json.loads(fields["data"])
    submission_id = uuid.UUID(data["submission_id"])
    raw_trials: list[dict] = data["trials"]
    runner_image_digest: str = data.get("runner_image_digest", "sha256:dev")

    # Discard warmup trials (spec §7.3).
    scoring_trials = raw_trials[_WARMUP_TRIALS:]
    if not scoring_trials:
        log.warning("pipeline.no_scoring_trials", submission_id=str(submission_id))
        return

    passed = [t for t in scoring_trials if t["framework_passed"] and not t["sandbox_violation"]]
    trials_passed = len(passed)
    trials_scored = len(scoring_trials)
    wall_ns_values = [t["wall_ns"] for t in scoring_trials]
    mem_kb_values = [t["mem_kb"] for t in scoring_trials]

    # Score correctness (spec §8.1).
    correctness, ci_lo, ci_hi = score_correctness(trials_passed, trials_scored)

    # Score reliability (spec §8.2).
    outcomes = [t["framework_passed"] and not t["sandbox_violation"] for t in scoring_trials]
    reliability, flaky = score_reliability(outcomes)

    # Non-determinism: framework_passed varies across scoring trials (spec §8.2).
    passed_outcomes = [t["framework_passed"] for t in scoring_trials]
    non_deterministic = len(set(passed_outcomes)) > 1 and len(scoring_trials) > 1

    # Wall time percentiles.
    arr = np.asarray(wall_ns_values, dtype=float)
    wall_ms_p50 = int(np.percentile(arr, 50) / 1_000_000)
    wall_ms_p95 = int(np.percentile(arr, 95) / 1_000_000)
    mem_peak_mb = int(max(mem_kb_values) / 1024) if mem_kb_values else None

    # Fetch submission metadata + baseline in a single connection.
    async with pool.acquire() as conn:
        sub = await conn.fetchrow(
            "SELECT tenant_id, model_id, language, prompt_hash, test_suite_hash "
            "FROM submissions WHERE id=$1",
            submission_id,
        )
        if sub is None:
            log.error("pipeline.submission_not_found", id=str(submission_id))
            return

        baseline_row = await conn.fetchrow(
            "SELECT median_wall_time_ns FROM baselines WHERE test_suite_hash=$1",
            sub["test_suite_hash"],
        )

    baseline_ns: int | None = baseline_row["median_wall_time_ns"] if baseline_row else None

    # Perf (spec §8.3) — normalize against Rust baseline.
    perf_normalized, perf_ci_lo, perf_ci_hi = score_perf(wall_ns_values, baseline_ns)

    # Build and sign attestation (spec §9).
    attestation_payload = {
        "version": "1.0",
        "submission_id": str(submission_id),
        "tenant_id": sub["tenant_id"],
        "model_id": sub["model_id"],
        "language": sub["language"],
        "prompt_hash": bytes(sub["prompt_hash"]).hex(),
        "test_suite_hash": bytes(sub["test_suite_hash"]).hex(),
        "runner_image_digest": runner_image_digest,
        "scheduler_version": data.get("scheduler_version", "0.1.0"),
        "scores": {
            "correctness": correctness,
            "correctness_ci": [ci_lo, ci_hi],
            "reliability": reliability,
            "perf_normalized": perf_normalized,
            "perf_ci": [perf_ci_lo, perf_ci_hi] if perf_ci_lo is not None else None,
            "non_deterministic": non_deterministic,
        },
        "trials": trials_scored,
        "scored_at": datetime.now(UTC).isoformat(),
    }
    signed_attestation, raw_sig = sign_attestation(attestation_payload)

    # Persist results + optional baseline upsert (spec §3.2 step 12).
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO results (
                    id, correctness_score, correctness_ci_lo, correctness_ci_hi,
                    reliability_score, flaky, non_deterministic,
                    perf_normalized, perf_ci_lo, perf_ci_hi,
                    trials_total, trials_passed,
                    wall_time_ms_p50, wall_time_ms_p95, mem_peak_mb,
                    attestation_sig, attestation_pubkey_id,
                    raw_trials, scored_at
                ) VALUES (
                    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,now()
                )
                ON CONFLICT (id) DO NOTHING
                """,
                submission_id,
                correctness, ci_lo, ci_hi,
                reliability, flaky, non_deterministic,
                perf_normalized, perf_ci_lo, perf_ci_hi,
                trials_scored, trials_passed,
                wall_ms_p50, wall_ms_p95, mem_peak_mb,
                raw_sig if raw_sig != b"dev-no-key" else b"\x00",
                signed_attestation.get("pubkey_id", "polyeval-dev"),
                json.dumps(scoring_trials),
            )
            updated = await conn.fetchval(
                """
                UPDATE submissions
                SET status='scored', version=3, updated_at=now()
                WHERE id=$1 AND version IN (1,2)
                RETURNING id
                """,
                submission_id,
            )
            if not updated:
                log.warning("pipeline.optimistic_lock_miss", id=str(submission_id))

            # Rust submissions define the performance baseline (spec §8.3).
            if sub["language"] == "rust" and wall_ns_values:
                from .stats.trim import trimmed_median
                rust_median_ns = int(trimmed_median(arr))
                rust_p95_ns = int(np.percentile(arr, 95))
                await conn.execute(
                    """
                    INSERT INTO baselines
                        (test_suite_hash, language, median_wall_time_ns, p95_wall_time_ns,
                         sample_count, refreshed_at)
                    VALUES ($1, 'rust', $2, $3, $4, now())
                    ON CONFLICT (test_suite_hash) DO UPDATE
                        SET median_wall_time_ns = EXCLUDED.median_wall_time_ns,
                            p95_wall_time_ns    = EXCLUDED.p95_wall_time_ns,
                            sample_count        = EXCLUDED.sample_count,
                            refreshed_at        = now()
                        WHERE baselines.sample_count <= EXCLUDED.sample_count
                    """,
                    sub["test_suite_hash"],
                    rust_median_ns,
                    rust_p95_ns,
                    len(scoring_trials),
                )
                log.info(
                    "pipeline.baseline_upserted",
                    test_suite_hash=bytes(sub["test_suite_hash"]).hex()[:16],
                    median_ns=rust_median_ns,
                )

    # Emit Prometheus metrics.
    lang = sub["language"]
    scored_total.labels(language=lang).inc()
    metric_correctness_score.observe(correctness)
    if non_deterministic:
        non_deterministic_total.labels(language=lang).inc()
    for t in scoring_trials:
        if t.get("sandbox_violation"):
            sandbox_violations_total.labels(language=lang).inc()
    scoring_duration_seconds.observe(datetime.now(UTC).timestamp() - t_entry_start)

    log.info(
        "pipeline.scored",
        id=str(submission_id),
        correctness=correctness,
        flaky=flaky,
        non_deterministic=non_deterministic,
        trials=trials_scored,
        language=lang,
    )
