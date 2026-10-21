"""drop task attempt columns

Revision ID: c2f9d4a7e8b1
Revises: a4c8e2f1b9d6
Create Date: 2026-10-21 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2f9d4a7e8b1"
down_revision: Union[str, Sequence[str], None] = "a4c8e2f1b9d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove retry state now that tasks fail immediately."""
    op.drop_column("tasks", "max_attempts")
    op.drop_column("tasks", "attempts")


def downgrade() -> None:
    """Restore the retry counters."""
    op.add_column(
        "tasks",
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "max_attempts",
            sa.Integer(),
            server_default=sa.text("3"),
            nullable=False,
        ),
    )
