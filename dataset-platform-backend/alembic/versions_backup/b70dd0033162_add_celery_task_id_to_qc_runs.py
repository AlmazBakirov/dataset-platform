"""add celery_task_id to qc_runs (idempotent)

Revision ID: b70dd0033162
Revises:
Create Date: 2026-01-28
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b70dd0033162"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # idempotent для Postgres
    op.execute(
        """
        ALTER TABLE qc_runs
        ADD COLUMN IF NOT EXISTS celery_task_id VARCHAR;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE qc_runs DROP COLUMN IF EXISTS celery_task_id;")
