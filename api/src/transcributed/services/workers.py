from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from transcributed.enums import TaskStatus
from transcributed.models import ProjectItem, Run, Task
from transcributed.schemas import WorkerRead, WorkersResponse


async def list_workers(
    session: AsyncSession,
    project_id: UUID | None = None,
    run_id: UUID | None = None,
) -> WorkersResponse:
    query = (
        select(Task)
        .join(Task.run)
        .where(Task.status.in_([TaskStatus.QUEUED, TaskStatus.PROCESSING]))
        .options(
            selectinload(Task.run).selectinload(Run.project),
            selectinload(Task.project_item).selectinload(ProjectItem.video),
        )
        .order_by(Task.started_at.asc().nulls_last(), Task.created_at.asc())
    )
    if project_id is not None:
        query = query.where(Run.project_id == project_id)
    if run_id is not None:
        query = query.where(Task.run_id == run_id)

    tasks = (await session.scalars(query)).all()
    active = sum(1 for task in tasks if task.status == TaskStatus.PROCESSING)
    workers = [
        WorkerRead(
            task_id=task.id,
            run_id=task.run_id,
            project_id=task.run.project_id,
            project_name=task.run.project.name,
            path=task.project_item.video.path,
            status=task.status,
            node=task.worker_node,
            pod=task.worker_pod,
            started_at=task.started_at,
            attempts=task.attempts,
            max_attempts=task.max_attempts,
            progress=task.progress,
        )
        for task in tasks
        if task.status == TaskStatus.PROCESSING
    ]

    return WorkersResponse(
        active=active,
        queued=len(tasks) - active,
        workers=workers,
    )
