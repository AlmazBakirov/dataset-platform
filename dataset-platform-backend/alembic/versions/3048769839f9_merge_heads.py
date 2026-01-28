"""merge heads

Revision ID: 3048769839f9
Revises: e7f8g9h0i1j2, c92f2c7a9b10, d8c3b8f2c1a4, 7f3c2a1b9d20
Create Date: 2026-01-28 14:15:19.221154

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "3048769839f9"
down_revision: Union[str, Sequence[str], None] = (
    "e7f8g9h0i1j2",
    "c92f2c7a9b10",
    "d8c3b8f2c1a4",
    "7f3c2a1b9d20",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
