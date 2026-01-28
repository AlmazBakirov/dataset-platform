"""make qc_runs.started_at nullable

Revision ID: 7f3c2a1b9d20
Revises: c91f2c7a9b10
Create Date: 2026-01-28
"""

from alembic import op
import sqlalchemy as sa

revision = "7f3c2a1b9d20"
down_revision = "c91f2c7a9b10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "qc_runs",
        "started_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )
    op.alter_column(
        "qc_runs",
        "finished_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )


def downgrade() -> None:
    # Откатить обратно в NOT NULL безопасно нельзя без заполнения данных.
    pass
