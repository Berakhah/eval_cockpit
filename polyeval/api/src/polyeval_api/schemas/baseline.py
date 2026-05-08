"""Baseline Pydantic models — spec §6 GET /v1/baselines/{test_suite_hash}."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BaselineInfo(BaseModel):
    test_suite_hash: str           # hex-encoded
    language: str
    median_wall_time_ns: int
    p95_wall_time_ns: int
    sample_count: int
    refreshed_at: datetime
