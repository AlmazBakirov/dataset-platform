"""make qc_runs started_at/finished_at nullable

Revision ID: e7f8g9h0i1j2
Revises: c91f2c7a9b10
Create Date: 2026-01-28
"""

from alembic import op

revision = "e7f8g9h0i1j2"
down_revision = "c91f2c7a9b10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: проверяем и только тогда DROP NOT NULL
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'qc_runs'
              AND column_name = 'started_at'
              AND is_nullable = 'NO'
          ) THEN
            ALTER TABLE qc_runs ALTER COLUMN started_at DROP NOT NULL;
          END IF;

          IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'qc_runs'
              AND column_name = 'finished_at'
              AND is_nullable = 'NO'
          ) THEN
            ALTER TABLE qc_runs ALTER COLUMN finished_at DROP NOT NULL;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # Обратно делать NOT NULL нельзя безопасно без заполнения данных.
    # Поэтому downgrade оставим пустым.
    pass
