"""Health endpoint response schemas. Stable contract — UI imports these via OpenAPI codegen."""

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness response."""

    status: Literal["ok"] = "ok"
    version: str = Field(..., description="Semantic version of the running API.")


class ReadinessResponse(BaseModel):
    """Readiness response. `checks` keys: db, redis, scheduler (spec §6)."""

    status: Literal["ok", "degraded"] = "ok"
    version: str
    checks: dict[str, Literal["ok", "fail", "skipped"]] = Field(
        default_factory=dict,
        description="Per-dependency health. 'skipped' until Slice 1 wires real probes.",
    )
