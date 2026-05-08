"""RLS tenant isolation + non_deterministic flag (spec §11, §8.2).

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Non-determinism flag: true when framework_passed is inconsistent across trials.
    op.execute("""
        ALTER TABLE results
        ADD COLUMN non_deterministic BOOLEAN NOT NULL DEFAULT FALSE
    """)

    # Row-Level Security on submissions.
    # Policy: row is visible when app.tenant_id is empty (aggregator/admin)
    # or when it matches the row's tenant_id (API calls via tenant_connection).
    op.execute("ALTER TABLE submissions ENABLE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY submissions_tenant_isolation ON submissions
        USING (
            current_setting('app.tenant_id', true) = ''
            OR tenant_id = current_setting('app.tenant_id', true)
        )
    """)

    # RLS on results via join to submissions (results has no tenant_id of its own).
    op.execute("ALTER TABLE results ENABLE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY results_tenant_isolation ON results
        USING (
            current_setting('app.tenant_id', true) = ''
            OR EXISTS (
                SELECT 1 FROM submissions
                WHERE submissions.id = results.id
                  AND (
                    current_setting('app.tenant_id', true) = ''
                    OR submissions.tenant_id = current_setting('app.tenant_id', true)
                  )
            )
        )
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS results_tenant_isolation ON results")
    op.execute("ALTER TABLE results DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS submissions_tenant_isolation ON submissions")
    op.execute("ALTER TABLE submissions DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE results DROP COLUMN IF EXISTS non_deterministic")
