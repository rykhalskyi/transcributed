from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

import structlog
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from transcributed.config import get_settings
from transcributed.enums import ProjectStatus, RunStatus, TaskStatus
from transcributed.errors import (
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)
from transcributed.models import Project, ProjectItem, Run, Task
from transcributed.services.spec import (
    build_effective_spec,
    resolve_input_path,
    source_matches,
    spec_hash,
)
from transcributed.services.status import refresh_run_status

settings = get_settings()
log = structlog.get_logger(__name__)


class TaskEnqueuer(Protocol):
    enabled: bool

    async def ensure_connected(self) -> bool: ...

    async def publish_task(self, task_id: UUID, run_id: UUID) -> bool: ...


async def has_active_run(session: AsyncSession, project_id: UUID) -> bool:
    active_run = await session.scalar(
        select(Run.id).where(
            Run.project_id == project_id,
            Run.status.in_([RunStatus.QUEUED, RunStatus.RUNNING]),
        )
    )
    return active_run is not None


async def _ensure_publisher_ready(publisher: TaskEnqueuer | None) -> None:
    if publisher is None or not publisher.enabled:
        return
    if not await publisher.ensure_connected():
        raise ServiceUnavailableError("Task queue is unavailable")


async def _compensate_failed_start(
    session: AsyncSession,
    run_id: UUID,
    project_id: UUID,
    previous_status: ProjectStatus,
) -> None:
    await session.execute(delete(Run).where(Run.id == run_id))
    project = await session.get(Project, project_id)
    if project is not None:
        project.status = previous_status
    await session.commit()


async def start_project(
    session: AsyncSession,
    project_id: UUID,
    publisher: TaskEnqueuer | None,
) -> tuple[Run, list[Task], int]:
    await _ensure_publisher_ready(publisher)

    project = await session.scalar(
        select(Project).where(Project.id == project_id).with_for_update()
    )
    if project is None:
        raise NotFoundError("Project not found")

    items = (
        await session.scalars(
            select(ProjectItem)
            .where(
                ProjectItem.project_id == project.id,
                ProjectItem.included.is_(True),
            )
            .options(selectinload(ProjectItem.video))
            .order_by(ProjectItem.position)
        )
    ).all()
    if not items:
        raise ConflictError("Project has no included items")

    active_run = await session.scalar(
        select(Run.id).where(
            Run.project_id == project.id,
            Run.status.in_([RunStatus.QUEUED, RunStatus.RUNNING]),
        )
    )
    if active_run is not None:
        raise ConflictError("Project already has an active run")

    problems: list[dict[str, str]] = []
    effective_specs: dict[UUID, dict] = {}
    for item in items:
        try:
            resolved = resolve_input_path(
                item.video.path,
                settings.nas_input_root,
                settings.allowed_extensions,
            )
            if not source_matches(
                item.video.size_bytes,
                item.video.mtime,
                resolved.size_bytes,
                resolved.mtime,
            ):
                problems.append(
                    {
                        "path": item.video.path,
                        "error": "Source file changed since it was added",
                    }
                )
                continue
            effective_specs[item.id] = build_effective_spec(
                project.defaults,
                item.spec_overrides,
            )
        except (OSError, ValidationError) as exc:
            problems.append({"path": item.video.path, "error": str(exc)})

    if problems:
        raise ConflictError("Project cannot be started", {"items": problems})

    run_spec = build_effective_spec(project.defaults, None)
    run = Run(
        project_id=project.id,
        status=RunStatus.QUEUED,
        spec=run_spec,
    )
    session.add(run)
    await session.flush()

    tasks = [
        Task(
            run_id=run.id,
            project_item_id=item.id,
            video_id=item.video_id,
            spec=effective_specs[item.id],
            spec_hash=spec_hash(effective_specs[item.id]),
            max_attempts=effective_specs[item.id]["max_attempts"],
        )
        for item in items
    ]
    session.add_all(tasks)

    previous_status = project.status
    project.status = ProjectStatus.ACTIVE

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("Project already has an active run") from exc

    enqueued = 0
    if publisher is not None and publisher.enabled:
        for task in tasks:
            try:
                published = await publisher.publish_task(task.id, run.id)
            except Exception:
                log.exception("publish_failed", task_id=str(task.id), run_id=str(run.id))
                published = False
            if not published:
                await _compensate_failed_start(
                    session,
                    run.id,
                    project.id,
                    previous_status,
                )
                raise ServiceUnavailableError("Failed to publish task to the queue")
            task.enqueued_at = datetime.now(UTC)
            enqueued += 1
        await session.commit()

    return run, tasks, enqueued


async def list_project_runs(
    session: AsyncSession,
    project_id: UUID,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[Run]:
    result = await session.scalars(
        select(Run)
        .where(Run.project_id == project_id)
        .order_by(Run.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.all()


async def get_run(session: AsyncSession, run_id: UUID) -> Run:
    run = await session.scalar(
        select(Run)
        .where(Run.id == run_id)
        .options(selectinload(Run.tasks).selectinload(Task.artifacts))
    )
    if run is None:
        raise NotFoundError("Run not found")
    return run


async def get_task(session: AsyncSession, task_id: UUID) -> Task:
    task = await session.scalar(
        select(Task).where(Task.id == task_id).options(selectinload(Task.artifacts))
    )
    if task is None:
        raise NotFoundError("Task not found")
    return task


TERMINAL_TASK_STATUSES = (
    TaskStatus.SUCCEEDED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
)
TERMINAL_RUN_STATUSES = (
    RunStatus.COMPLETED,
    RunStatus.PARTIALLY_FAILED,
    RunStatus.FAILED,
    RunStatus.CANCELLED,
)


async def cancel_task(session: AsyncSession, task_id: UUID) -> Task:
    task = await session.scalar(
        select(Task).where(Task.id == task_id).with_for_update()
    )
    if task is None:
        raise NotFoundError("Task not found")
    if task.status in TERMINAL_TASK_STATUSES:
        raise ConflictError("Task is already finished")

    task.status = TaskStatus.CANCELLED
    task.error = "cancelled by user"
    task.finished_at = datetime.now(UTC)
    await session.flush()
    await refresh_run_status(session, task.run_id)
    await session.commit()
    return await get_task(session, task_id)


async def cancel_run(session: AsyncSession, run_id: UUID) -> Run:
    run = await session.get(Run, run_id)
    if run is None:
        raise NotFoundError("Run not found")
    if run.status in TERMINAL_RUN_STATUSES:
        raise ConflictError("Run is already finished")

    tasks = (
        await session.scalars(
            select(Task)
            .where(
                Task.run_id == run_id,
                Task.status.in_([TaskStatus.QUEUED, TaskStatus.PROCESSING]),
            )
            .with_for_update()
        )
    ).all()

    now = datetime.now(UTC)
    for task in tasks:
        task.status = TaskStatus.CANCELLED
        task.error = "cancelled by user"
        task.finished_at = now

    await session.flush()
    await refresh_run_status(session, run_id)
    await session.commit()
    return await get_run(session, run_id)
