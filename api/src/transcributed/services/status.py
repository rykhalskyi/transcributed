from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from transcributed.enums import ProjectStatus, RunStatus, TaskStatus
from transcributed.models import Project, Run, Task


async def refresh_run_status(session: AsyncSession, run_id: UUID) -> Run | None:
    run = await session.scalar(
        select(Run).where(Run.id == run_id).with_for_update()
    )
    if run is None:
        return None

    rows = (
        await session.execute(
            select(Task.status, func.count(Task.id))
            .where(Task.run_id == run_id)
            .group_by(Task.status)
        )
    ).all()
    counts: dict[TaskStatus, int] = {}
    for status, count in rows:
        key = status if isinstance(status, TaskStatus) else TaskStatus(status)
        counts[key] = count

    total = sum(counts.values())
    if total == 0:
        return run

    queued = counts.get(TaskStatus.QUEUED, 0)
    processing = counts.get(TaskStatus.PROCESSING, 0)
    succeeded = counts.get(TaskStatus.SUCCEEDED, 0)
    failed = counts.get(TaskStatus.FAILED, 0)
    now = datetime.now(UTC)

    if queued or processing:
        run.status = RunStatus.RUNNING if processing else RunStatus.QUEUED
        if processing and run.started_at is None:
            run.started_at = now
        run.finished_at = None
    else:
        run.finished_at = now
        if failed == 0 and succeeded == total:
            run.status = RunStatus.COMPLETED
        elif succeeded == 0 and failed == total:
            run.status = RunStatus.FAILED
        else:
            run.status = RunStatus.PARTIALLY_FAILED

    project = await session.get(Project, run.project_id)
    if project is not None:
        if run.status == RunStatus.COMPLETED:
            project.status = ProjectStatus.COMPLETED
        elif run.status == RunStatus.FAILED:
            project.status = ProjectStatus.FAILED
        elif run.status == RunStatus.PARTIALLY_FAILED:
            project.status = ProjectStatus.PARTIALLY_FAILED
        elif run.status in (RunStatus.QUEUED, RunStatus.RUNNING):
            project.status = ProjectStatus.ACTIVE

    return run
