"""Liveness + readiness endpoints. Spec §6 API surface."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from .. import __version__
from ..schemas.health import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get(
    "/healthz",
    response_model=HealthResponse,
    summary="Liveness probe",
)
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@router.get(
    "/readyz",
    response_model=ReadinessResponse,
    summary="Readiness probe (db + redis + scheduler heartbeat)",
)
async def readyz() -> JSONResponse:
    """Slice 0: returns ok. Slice 1 wires real db + redis checks."""
    body = ReadinessResponse(
        status="ok",
        version=__version__,
        checks={"db": "skipped", "redis": "skipped", "scheduler": "skipped"},
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=body.model_dump())
