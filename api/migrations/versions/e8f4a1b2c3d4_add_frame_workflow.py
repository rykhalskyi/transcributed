"""add frame extraction workflow

Revision ID: e8f4a1b2c3d4
Revises: c2f9d4a7e8b1
Create Date: 2026-11-02 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8f4a1b2c3d4"
down_revision: Union[str, Sequence[str], None] = "c2f9d4a7e8b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add workflow selection, timecode files, and extracted frames."""
    op.add_column(
        "projects",
        sa.Column(
            "workflow",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'transcribe'"),
        ),
    )
    op.create_check_constraint(
        "workflow",
        "projects",
        "workflow IN ('transcribe', 'frames')",
    )

    op.add_column(
        "tasks",
        sa.Column(
            "frames_extracted",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "frames_skipped",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.create_table(
        "timecode_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mtime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timecodes_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "path",
            "size_bytes",
            "mtime",
            name="uq_timecode_files_path_size_mtime",
        ),
    )

    op.add_column(
        "project_items",
        sa.Column("timecode_file_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_project_items_timecode_file_id",
        "project_items",
        "timecode_files",
        ["timecode_file_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_project_items_timecode_file_id"),
        "project_items",
        ["timecode_file_id"],
        unique=False,
    )

    op.create_table(
        "task_frames",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("timecode_seconds", sa.Float(), nullable=False),
        sa.Column("timecode", sa.String(length=20), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "filename", name="uq_task_frames_task_filename"),
    )
    op.create_index(op.f("ix_task_frames_task_id"), "task_frames", ["task_id"], unique=False)
    op.create_index(
        "ix_task_frames_task_id_index",
        "task_frames",
        ["task_id", "index"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the frame extraction workflow."""
    op.drop_index("ix_task_frames_task_id_index", table_name="task_frames")
    op.drop_index(op.f("ix_task_frames_task_id"), table_name="task_frames")
    op.drop_table("task_frames")

    op.drop_index(op.f("ix_project_items_timecode_file_id"), table_name="project_items")
    op.drop_constraint(
        "fk_project_items_timecode_file_id",
        "project_items",
        type_="foreignkey",
    )
    op.drop_column("project_items", "timecode_file_id")
    op.drop_table("timecode_files")

    op.drop_column("tasks", "frames_skipped")
    op.drop_column("tasks", "frames_extracted")

    op.drop_constraint("workflow", "projects", type_="check")
    op.drop_column("projects", "workflow")
