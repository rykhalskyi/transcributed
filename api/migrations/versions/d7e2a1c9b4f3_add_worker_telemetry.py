"""add worker telemetry

Revision ID: d7e2a1c9b4f3
Revises: f1a2b3c4d5e6
Create Date: 2026-10-20 16:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7e2a1c9b4f3"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Track the worker pod and node on each task."""
    op.add_column("tasks", sa.Column("worker_pod", sa.String(length=253), nullable=True))
    op.add_column("tasks", sa.Column("worker_node", sa.String(length=253), nullable=True))


def downgrade() -> None:
    """Remove worker telemetry."""
    op.drop_column("tasks", "worker_node")
    op.drop_column("tasks", "worker_pod")
