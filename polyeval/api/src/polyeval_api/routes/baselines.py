"""Baseline inspection endpoints — spec §6.

GET  /v1/baselines/{test_suite_hash}  — return stored Rust baseline for a test suite.
POST /v1/baselines/refresh            — admin: trigger re-run of Rust baseline (202).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..db.session import get_db
from ..schemas.baseline import BaselineInfo

router = APIRouter(prefix="/v1/baselines", tags=["baselines"])


@router.get("/{test_suite_hash}", response_model=BaselineInfo)
async def get_baseline(
    test_suite_hash: str,
    conn=Depends(get_db),
) -> BaselineInfo:
    """Return Rust baseline for a test suite hash (hex-encoded 32-byte value)."""
    try:
        hash_bytes = bytes.fromhex(test_suite_hash)
    except ValueError:
        raise HTTPException(status_code=400, detail="test_suite_hash must be hex-encoded bytes")

    row = await conn.fetchrow(
        """
        SELECT test_suite_hash, language, median_wall_time_ns,
               p95_wall_time_ns, sample_count, refreshed_at
        FROM baselines
        WHERE test_suite_hash = $1
        """,
        hash_bytes,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="baseline not found for this test_suite_hash")

    return BaselineInfo(
        test_suite_hash=bytes(row["test_suite_hash"]).hex(),
        language=row["language"],
        median_wall_time_ns=row["median_wall_time_ns"],
        p95_wall_time_ns=row["p95_wall_time_ns"],
        sample_count=row["sample_count"],
        refreshed_at=row["refreshed_at"],
    )


@router.post("/refresh", status_code=202)
async def refresh_baseline() -> dict:
    """Admin endpoint: schedule a Rust baseline re-run.

    Full re-run scheduling is a Slice 3+ feature. Returns 202 Accepted
    with a message indicating the baseline will refresh on next Rust submission.
    """
    return {
        "status": "accepted",
        "message": "Baseline will be updated on the next scored Rust submission for this test suite.",
    }
