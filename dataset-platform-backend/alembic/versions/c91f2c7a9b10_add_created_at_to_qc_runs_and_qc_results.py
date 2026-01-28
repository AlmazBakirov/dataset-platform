"""add created_at to qc_runs and qc_results (idempotent)

Revision ID: c91f2c7a9b10
Revises: b70dd0033162
Create Date: 2026-01-28
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "c91f2c7a9b10"
down_revision = "b70dd0033162"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Postgres: безопасно, если колонка уже существует
    op.execute(
        """
        ALTER TABLE qc_runs
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
        """
    )

    # На практике часто всплывает следом (schema требует created_at)
    op.execute(
        """
        ALTER TABLE qc_results
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE qc_results DROP COLUMN IF EXISTS created_at;")
    op.execute("ALTER TABLE qc_runs DROP COLUMN IF EXISTS created_at;")
