"""add created_at to qc_runs and qc_results

Revision ID: c92f2c7a9b10
Revises: c91f2c7a9b10
Create Date: 2026-01-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# --- Alembic identifiers ---
revision = "c92f2c7a9b10"
down_revision = "c91f2c7a9b10"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = insp.get_columns(table_name)
    return any(c["name"] == column_name for c in cols)


def upgrade() -> None:
    # qc_runs.created_at
    if not _has_column("qc_runs", "created_at"):
        op.add_column(
            "qc_runs",
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )

    # qc_results.created_at
    if not _has_column("qc_results", "created_at"):
        op.add_column(
            "qc_results",
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    # Drop only if exists (safe for dev DBs)
    if _has_column("qc_results", "created_at"):
        op.drop_column("qc_results", "created_at")

    if _has_column("qc_runs", "created_at"):
        op.drop_column("qc_runs", "created_at")
