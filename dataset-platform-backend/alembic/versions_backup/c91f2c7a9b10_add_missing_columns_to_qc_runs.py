"""add missing columns to qc_runs (timestamps + nullable started_at)

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
    # 1) created_at: NOT NULL, default now()
    op.execute(
        """
        ALTER TABLE qc_runs
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
        """
    )

    # 2) started_at: nullable (queued run can have NULL)
    op.execute(
        """
        ALTER TABLE qc_runs
        ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ NULL;
        """
    )
    # If column existed but was NOT NULL, drop constraint.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name='qc_runs' AND column_name='started_at'
          ) THEN
            ALTER TABLE qc_runs ALTER COLUMN started_at DROP NOT NULL;
          END IF;
        END $$;
        """
    )

    # 3) finished_at: nullable
    op.execute(
        """
        ALTER TABLE qc_runs
        ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ NULL;
        """
    )

    # 4) celery_task_id: just in case (у тебя уже есть миграция, но делаем upgrade идемпотентным)
    op.execute(
        """
        ALTER TABLE qc_runs
        ADD COLUMN IF NOT EXISTS celery_task_id VARCHAR;
        """
    )

    # 5) params: если вдруг отсутствует (в некоторых БД бывает)
    op.execute(
        """
        ALTER TABLE qc_runs
        ADD COLUMN IF NOT EXISTS params JSON NOT NULL DEFAULT '{}'::json;
        """
    )

    # 6) подстраховка: если вдруг есть старые строки без created_at
    op.execute(
        """
        UPDATE qc_runs SET created_at = now() WHERE created_at IS NULL;
        """
    )


def downgrade() -> None:
    # Откат не делаем, чтобы не терять данные (и потому что миграция "repair"-типа).
    pass
