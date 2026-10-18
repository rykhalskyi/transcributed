from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from transcributed.config import get_settings
from transcributed.enums import ProjectStatus, RunStatus
from transcributed.errors import ConflictError, NotFoundError, ValidationError
from transcributed.models import Project, ProjectItem, Run, Task
from transcributed.services.spec import (
    build_effective_spec,
    resolve_input_path,
    source_matches,
    spec_hash,
)

settings = get_settings()
log = structlog.get_logger(__name__)


class TaskEnqueuer(Protocol):
    enabled: bool

    async def publish_task(self, task_id: UUID, run_id: UUID) -> bool: ...


async def start_project(
    session: AsyncSession,
    project: Project,
    publisher: TaskEnqueuer | None,
) -> tuple[Run, list[Task], int]:
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
            if published:
                task.enqueued_at = datetime.now(UTC)
                enqueued += 1
        await session.commit()

    return run, tasks, enqueued


async def list_project_runs(
    session: AsyncSession,
    project_id: UUID,
) -> Sequence[Run]:
    result = await session.scalars(
        select(Run).where(Run.project_id == project_id).order_by(Run.created_at.desc())
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
