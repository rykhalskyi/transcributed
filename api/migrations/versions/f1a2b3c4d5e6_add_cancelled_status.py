"""add cancelled status

Revision ID: f1a2b3c4d5e6
Revises: b93eb547adce
Create Date: 2026-10-18 20:30:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "b93eb547adce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PROJECT_STATUSES = "'draft', 'active', 'completed', 'partially_failed', 'failed', 'cancelled'"
RUN_STATUSES = "'queued', 'running', 'completed', 'partially_failed', 'failed', 'cancelled'"
TASK_STATUSES = "'queued', 'processing', 'succeeded', 'failed', 'cancelled'"

OLD_PROJECT_STATUSES = "'draft', 'active', 'completed', 'partially_failed', 'failed'"
OLD_RUN_STATUSES = "'queued', 'running', 'completed', 'partially_failed', 'failed'"
OLD_TASK_STATUSES = "'queued', 'processing', 'succeeded', 'failed'"


def upgrade() -> None:
    """Add the cancelled status to projects, runs, and tasks."""
    op.drop_constraint("projectstatus", "projects", type_="check")
    op.create_check_constraint(
        "projectstatus",
        "projects",
        f"status IN ({PROJECT_STATUSES})",
    )

    op.drop_constraint("runstatus", "runs", type_="check")
    op.create_check_constraint(
        "runstatus",
        "runs",
        f"status IN ({RUN_STATUSES})",
    )

    op.drop_constraint("taskstatus", "tasks", type_="check")
    op.create_check_constraint(
        "taskstatus",
        "tasks",
        f"status IN ({TASK_STATUSES})",
    )


def downgrade() -> None:
    """Remove the cancelled status, mapping cancelled rows to failed."""
    op.execute("UPDATE projects SET status = 'failed' WHERE status = 'cancelled'")
    op.execute("UPDATE runs SET status = 'failed' WHERE status = 'cancelled'")
    op.execute("UPDATE tasks SET status = 'failed' WHERE status = 'cancelled'")

    op.drop_constraint("taskstatus", "tasks", type_="check")
    op.create_check_constraint(
        "taskstatus",
        "tasks",
        f"status IN ({OLD_TASK_STATUSES})",
    )

    op.drop_constraint("runstatus", "runs", type_="check")
    op.create_check_constraint(
        "runstatus",
        "runs",
        f"status IN ({OLD_RUN_STATUSES})",
    )

    op.drop_constraint("projectstatus", "projects", type_="check")
    op.create_check_constraint(
        "projectstatus",
        "projects",
        f"status IN ({OLD_PROJECT_STATUSES})",
    )
