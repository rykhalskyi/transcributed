"""add task progress

Revision ID: a4c8e2f1b9d6
Revises: d7e2a1c9b4f3
Create Date: 2026-10-20 18:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4c8e2f1b9d6"
down_revision: Union[str, Sequence[str], None] = "d7e2a1c9b4f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Track transcription progress as a percentage."""
    op.add_column(
        "tasks",
        sa.Column("progress", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    """Remove transcription progress."""
    op.drop_column("tasks", "progress")
