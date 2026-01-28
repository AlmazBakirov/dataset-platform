"""add timestamps to qc_runs (idempotent)

Revision ID: d8c3b8f2c1a4
Revises: c91f2c7a9b10
Create Date: 2026-01-28
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "d8c3b8f2c1a4"
down_revision = "c91f2c7a9b10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent для Postgres
    op.execute(
        """
        ALTER TABLE qc_runs
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ;
        """
    )
    op.execute(
        """
        ALTER TABLE qc_runs
        ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
        """
    )
    op.execute(
        """
        ALTER TABLE qc_runs
        ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ;
        """
    )

    # (Опционально) если уже есть старые строки — проставим created_at, чтобы не было NULL
    op.execute(
        """
        UPDATE qc_runs
        SET created_at = NOW()
        WHERE created_at IS NULL;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE qc_runs DROP COLUMN IF EXISTS finished_at;")
    op.execute("ALTER TABLE qc_runs DROP COLUMN IF EXISTS started_at;")
    op.execute("ALTER TABLE qc_runs DROP COLUMN IF EXISTS created_at;")
