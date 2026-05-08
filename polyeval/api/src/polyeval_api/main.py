"""FastAPI app entrypoint."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from . import __version__
from .db import close_pool, init_pool
from .routes.baselines import router as baselines_router
from .routes.health import router as health_router
from .routes.submissions import router as submissions_router
from .settings import get_settings
from .telemetry import configure_logging, configure_tracing

log = structlog.get_logger()

_HMAC_MIN_LEN = 32


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_tracing(settings.otel_endpoint, service_name="polyeval-api")
    if settings.environment == "prod" and len(settings.hmac_secret) < _HMAC_MIN_LEN:
        raise RuntimeError(
            f"POLYEVAL_HMAC_SECRET must be ≥{_HMAC_MIN_LEN} bytes in production"
        )
    await init_pool(settings)
    log.info("api.startup", version=__version__, environment=settings.environment)
    yield
    await close_pool()
    log.info("api.shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="PolyEval API",
        description=(
            "Multi-language LLM code evaluation harness. "
            "All endpoints require HMAC-SHA256 signing over the raw body "
            "(see spec §6, §12.1)."
        ),
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )

    app.include_router(health_router)
    app.include_router(submissions_router)
    app.include_router(baselines_router)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> PlainTextResponse:
        return PlainTextResponse(
            content=generate_latest().decode("utf-8"),
            media_type=CONTENT_TYPE_LATEST,
        )

    FastAPIInstrumentor.instrument_app(app)

    return app


app = create_app()


def run() -> None:
    """Console-script entrypoint for `polyeval-api`."""
    import uvicorn

    uvicorn.run(
        "polyeval_api.main:app",
        host="0.0.0.0",  # noqa: S104 — bound inside container
        port=8000,
        log_config=None,
    )
