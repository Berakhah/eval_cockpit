"""Initial schema: submissions, results, baselines (spec §5.1).

Revision ID: 0001
Revises:
Create Date: 2026-05-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE submissions (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       TEXT NOT NULL,
            model_id        TEXT NOT NULL,
            language        TEXT NOT NULL
                CHECK (language IN ('python','javascript','java','cpp','rust')),
            prompt_hash     BYTEA NOT NULL,
            test_suite_hash BYTEA NOT NULL,
            code            BYTEA NOT NULL,
            status          TEXT NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued','running','scored','failed')),
            version         INTEGER NOT NULL DEFAULT 1,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE INDEX idx_subs_status
            ON submissions(status)
            WHERE status IN ('queued', 'running')
    """)

    op.execute("""
        CREATE INDEX idx_subs_tenant_created
            ON submissions(tenant_id, created_at DESC)
    """)

    op.execute("""
        CREATE TABLE results (
            id                   UUID PRIMARY KEY
                REFERENCES submissions(id) ON DELETE CASCADE,
            correctness_score    NUMERIC(5,4) NOT NULL,
            correctness_ci_lo    NUMERIC(5,4) NOT NULL,
            correctness_ci_hi    NUMERIC(5,4) NOT NULL,
            reliability_score    NUMERIC(5,4) NOT NULL,
            flaky                BOOLEAN NOT NULL DEFAULT FALSE,
            perf_normalized      NUMERIC(9,4),
            perf_ci_lo           NUMERIC(9,4),
            perf_ci_hi           NUMERIC(9,4),
            trials_total         INTEGER NOT NULL,
            trials_passed        INTEGER NOT NULL,
            wall_time_ms_p50     BIGINT NOT NULL,
            wall_time_ms_p95     BIGINT NOT NULL,
            mem_peak_mb          INTEGER,
            attestation_sig      BYTEA NOT NULL,
            attestation_pubkey_id TEXT NOT NULL,
            raw_trials           JSONB NOT NULL DEFAULT '[]',
            scored_at            TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE baselines (
            test_suite_hash     BYTEA PRIMARY KEY,
            language            TEXT NOT NULL,
            median_wall_time_ns BIGINT NOT NULL,
            p95_wall_time_ns    BIGINT NOT NULL,
            sample_count        INTEGER NOT NULL,
            refreshed_at        TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS baselines")
    op.execute("DROP TABLE IF EXISTS results")
    op.execute("DROP TABLE IF EXISTS submissions")
