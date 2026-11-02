"""store uploaded timecode files

Revision ID: f7b3c2d1a9e8
Revises: e8f4a1b2c3d4
Create Date: 2026-11-02 20:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7b3c2d1a9e8"
down_revision: Union[str, Sequence[str], None] = "e8f4a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Replace NAS timecode references with uploaded file content."""
    op.add_column(
        "timecode_files",
        sa.Column("filename", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "timecode_files",
        sa.Column("content", sa.Text(), nullable=True),
    )
    op.execute(
        "UPDATE timecode_files "
        "SET filename = regexp_replace(path, '^.*/', ''), "
        "content = ''"
    )
    op.alter_column("timecode_files", "filename", nullable=False)
    op.alter_column("timecode_files", "content", nullable=False)

    op.drop_constraint(
        "uq_timecode_files_path_size_mtime",
        "timecode_files",
        type_="unique",
    )
    op.drop_column("timecode_files", "mtime")
    op.drop_column("timecode_files", "size_bytes")
    op.drop_column("timecode_files", "path")


def downgrade() -> None:
    """Restore NAS timecode references."""
    op.add_column(
        "timecode_files",
        sa.Column("path", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "timecode_files",
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "timecode_files",
        sa.Column("mtime", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE timecode_files "
        "SET path = filename || '/' || id::text, size_bytes = 0, mtime = now()"
    )
    op.alter_column("timecode_files", "path", nullable=False)
    op.alter_column("timecode_files", "size_bytes", nullable=False)
    op.alter_column("timecode_files", "mtime", nullable=False)
    op.create_unique_constraint(
        "uq_timecode_files_path_size_mtime",
        "timecode_files",
        ["path", "size_bytes", "mtime"],
    )

    op.drop_column("timecode_files", "content")
    op.drop_column("timecode_files", "filename")
