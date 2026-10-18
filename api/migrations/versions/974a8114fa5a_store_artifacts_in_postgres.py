"""store artifacts in postgres

Revision ID: 974a8114fa5a
Revises: 10874d9a8b30
Create Date: 2026-10-18 14:07:01.929649

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "974a8114fa5a"
down_revision: Union[str, Sequence[str], None] = "10874d9a8b30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("artifacts", sa.Column("filename", sa.String(length=255), nullable=True))
    op.add_column("artifacts", sa.Column("content_type", sa.String(length=100), nullable=True))
    op.add_column("artifacts", sa.Column("content", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE artifacts
        SET filename = CASE
                WHEN format = 'metadata' THEN 'metadata.json'
                ELSE 'transcript.' || format
            END,
            content_type = CASE
                WHEN format = 'vtt' THEN 'text/vtt; charset=utf-8'
                WHEN format = 'txt' THEN 'text/plain; charset=utf-8'
                ELSE 'application/json'
            END
        """
    )
    op.alter_column("artifacts", "filename", nullable=False)
    op.alter_column("artifacts", "content_type", nullable=False)
    op.alter_column("artifacts", "path", existing_type=sa.Text(), nullable=True)
    op.drop_column("tasks", "output_dir")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("tasks", sa.Column("output_dir", sa.Text(), nullable=True))
    op.execute("UPDATE artifacts SET path = '' WHERE path IS NULL")
    op.alter_column("artifacts", "path", existing_type=sa.Text(), nullable=False)
    op.drop_column("artifacts", "content")
    op.drop_column("artifacts", "content_type")
    op.drop_column("artifacts", "filename")
