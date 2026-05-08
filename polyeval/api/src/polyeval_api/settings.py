"""Runtime configuration sourced from environment variables (spec §10)."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POLYEVAL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_url: str = Field(
        default="postgresql+asyncpg://polyeval:polyeval@postgres:5432/polyeval",
        description="Async Postgres URL. Required.",
    )
    redis_url: str = Field(
        default="redis://redis:6379/0",
        description="Redis URL for streams + cache. Required.",
    )
    hmac_secret: str = Field(
        default="",
        description="HMAC secret for request signing (≥32 bytes). Required in production.",
        min_length=0,  # 0 allows empty for dev; validated at startup — see main.py lifespan
        max_length=512,
    )
    # Hard min enforced at startup rather than Pydantic so the error message is clear.
    # In production POLYEVAL_ENVIRONMENT=prod the lifespan raises if len < 32.
    ed25519_privkey_path: Path = Field(
        default=Path("/run/secrets/eval-signer.key"),
        description="Path to Ed25519 private key for attestation signing.",
    )
    otel_endpoint: str = Field(
        default="http://otel-collector:4317",
        description="OTLP gRPC endpoint.",
    )
    runner_timeout_default_s: float = Field(default=5.0, ge=0.1, le=30.0)
    max_concurrent_runners: int = Field(default=4, ge=1, le=64)
    cache_ttl_days: int = Field(default=30, ge=1, le=365)
    baseline_refresh_interval_h: int = Field(default=168, ge=1)

    environment: Literal["dev", "test", "staging", "prod"] = Field(default="dev")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")


def get_settings() -> Settings:
    return Settings()
