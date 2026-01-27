"""add celery_task_id to qc_runs

Revision ID: b70dd0033162
Revises:
Create Date: 2026-01-26 21:00:51.792722

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b70dd0033162"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "qc_runs", sa.Column("celery_task_id", sa.String(length=255), nullable=True)
    )
    op.create_index(
        "ix_qc_runs_celery_task_id", "qc_runs", ["celery_task_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_qc_runs_celery_task_id", table_name="qc_runs")
    op.drop_column("qc_runs", "celery_task_id")
