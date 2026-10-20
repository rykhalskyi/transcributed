from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer, selectinload

from transcributed.config import get_settings
from transcributed.enums import ProjectStatus
from transcributed.errors import ConflictError, NotFoundError, ValidationError
from transcributed.models import Artifact, Project, ProjectItem, Task
from transcributed.schemas import (
    ArtifactRead,
    ProjectCreate,
    ProjectItemRead,
    ProjectItemResult,
    ProjectItemsAddRequest,
    ProjectItemsAddResponse,
    ProjectItemUpdate,
    ProjectUpdate,
)
from transcributed.services.runs import has_active_run
from transcributed.services.spec import build_effective_spec, resolve_input_path
from transcributed.services.videos import get_or_create_video

settings = get_settings()


async def create_project(session: AsyncSession, payload: ProjectCreate) -> Project:
    project = Project(
        name=payload.name,
        description=payload.description,
        defaults=payload.defaults.model_dump(),
        status=ProjectStatus.DRAFT,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def list_projects(
    session: AsyncSession,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[Project]:
    result = await session.scalars(
        select(Project).order_by(Project.created_at.desc()).limit(limit).offset(offset)
    )
    return result.all()


async def get_project(session: AsyncSession, project_id: UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError("Project not found")
    return project


async def get_project_for_update(session: AsyncSession, project_id: UUID) -> Project:
    project = await session.scalar(
        select(Project).where(Project.id == project_id).with_for_update()
    )
    if project is None:
        raise NotFoundError("Project not found")
    return project


async def update_project(
    session: AsyncSession,
    project: Project,
    payload: ProjectUpdate,
) -> Project:
    if await has_active_run(session, project.id):
        raise ConflictError("Project cannot be edited while a run is active")

    data = payload.model_dump(exclude_unset=True)
    if "defaults" in data and data["defaults"] is not None:
        defaults = payload.defaults
        assert defaults is not None
        data["defaults"] = defaults.model_dump()
    if not data:
        return project

    for field, value in data.items():
        setattr(project, field, value)

    await session.commit()
    await session.refresh(project)
    return project


async def delete_project(session: AsyncSession, project: Project) -> None:
    if await has_active_run(session, project.id):
        raise ConflictError("Project cannot be deleted while a run is active")
    await session.delete(project)
    await session.commit()


async def add_items(
    session: AsyncSession,
    project: Project,
    request: ProjectItemsAddRequest,
) -> ProjectItemsAddResponse:
    if await has_active_run(session, project.id):
        raise ConflictError("Items cannot be added while a run is active")

    if len(request.items) > settings.max_batch_items:
        raise ValidationError(
            f"A project can add at most {settings.max_batch_items} items per request"
        )

    max_position = await session.scalar(
        select(func.coalesce(func.max(ProjectItem.position), 0)).where(
            ProjectItem.project_id == project.id
        )
    )
    next_position = int(max_position or 0) + 1

    results: list[ProjectItemResult] = []
    accepted = 0
    rejected = 0

    for item_input in request.items:
        try:
            resolved = resolve_input_path(
                item_input.path,
                settings.nas_input_root,
                settings.allowed_extensions,
            )
            video = await get_or_create_video(session, resolved)

            existing = await session.scalar(
                select(ProjectItem).where(
                    ProjectItem.project_id == project.id,
                    ProjectItem.video_id == video.id,
                )
            )
            if existing is not None:
                results.append(
                    ProjectItemResult(
                        path=resolved.relative_path,
                        accepted=True,
                        created=False,
                        item_id=existing.id,
                    )
                )
                accepted += 1
                continue

            overrides: dict[str, str] = {}
            if item_input.language is not None:
                overrides["language"] = item_input.language
            if item_input.model is not None:
                overrides["model"] = item_input.model
            build_effective_spec(project.defaults, overrides or None)

            item = ProjectItem(
                project_id=project.id,
                video_id=video.id,
                position=next_position,
                spec_overrides=overrides or None,
            )
            session.add(item)
            await session.flush()
            next_position += 1

            results.append(
                ProjectItemResult(
                    path=resolved.relative_path,
                    accepted=True,
                    created=True,
                    item_id=item.id,
                )
            )
            accepted += 1
        except (OSError, ValidationError) as exc:
            rejected += 1
            results.append(
                ProjectItemResult(
                    path=item_input.path,
                    accepted=False,
                    error=str(exc),
                )
            )

    await session.commit()
    return ProjectItemsAddResponse(
        accepted=accepted,
        rejected=rejected,
        results=results,
    )


async def _load_artifacts(
    session: AsyncSession,
    task_ids: list[UUID],
) -> dict[UUID, list[Artifact]]:
    if not task_ids:
        return {}
    artifacts = (
        await session.scalars(
            select(Artifact)
            .where(Artifact.task_id.in_(task_ids))
            .options(defer(Artifact.content))
            .order_by(Artifact.format)
        )
    ).all()
    grouped: dict[UUID, list[Artifact]] = {}
    for artifact in artifacts:
        grouped.setdefault(artifact.task_id, []).append(artifact)
    return grouped


def _to_item_read(
    item: ProjectItem,
    latest_task: Task | None,
    latest_task_artifacts: list[Artifact],
) -> ProjectItemRead:
    return ProjectItemRead(
        id=item.id,
        project_id=item.project_id,
        video_id=item.video_id,
        path=item.video.path,
        position=item.position,
        included=item.included,
        spec_overrides=item.spec_overrides,
        latest_task_status=(latest_task.status if latest_task is not None else None),
        latest_task_id=(latest_task.id if latest_task is not None else None),
        latest_task_progress=(latest_task.progress if latest_task is not None else None),
        latest_task_artifacts=[
            ArtifactRead.model_validate(artifact) for artifact in latest_task_artifacts
        ],
    )


async def list_project_items(
    session: AsyncSession,
    project_id: UUID,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[ProjectItemRead]:
    items = (
        await session.scalars(
            select(ProjectItem)
            .where(ProjectItem.project_id == project_id)
            .options(selectinload(ProjectItem.video))
            .order_by(ProjectItem.position)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    if not items:
        return []

    task_rows = (
        await session.scalars(
            select(Task)
            .where(Task.project_item_id.in_([item.id for item in items]))
            .ext(distinct_on(Task.project_item_id))
            .order_by(Task.project_item_id, Task.created_at.desc())
        )
    ).all()
    latest_tasks = {task.project_item_id: task for task in task_rows}
    artifacts = await _load_artifacts(
        session,
        [task.id for task in latest_tasks.values()],
    )

    result: list[ProjectItemRead] = []
    for item in items:
        latest_task = latest_tasks.get(item.id)
        result.append(
            _to_item_read(
                item,
                latest_task,
                artifacts.get(latest_task.id, []) if latest_task is not None else [],
            )
        )
    return result


async def update_item(
    session: AsyncSession,
    project: Project,
    item_id: UUID,
    payload: ProjectItemUpdate,
) -> ProjectItemRead:
    if await has_active_run(session, project.id):
        raise ConflictError("Items cannot be edited while a run is active")

    item = await session.scalar(
        select(ProjectItem)
        .where(
            ProjectItem.id == item_id,
            ProjectItem.project_id == project.id,
        )
        .options(selectinload(ProjectItem.video))
    )
    if item is None:
        raise NotFoundError("Project item not found")

    data = payload.model_dump(exclude_unset=True)

    if data.get("included") is not None:
        item.included = data["included"]

    overrides = dict(item.spec_overrides or {})
    overrides_changed = False
    for key in ("language", "model"):
        if key not in data:
            continue
        overrides_changed = True
        if data[key] is None:
            overrides.pop(key, None)
        else:
            overrides[key] = data[key]

    if overrides_changed:
        build_effective_spec(project.defaults, overrides or None)
        item.spec_overrides = overrides or None

    await session.commit()

    latest_task = await session.scalar(
        select(Task)
        .where(Task.project_item_id == item.id)
        .order_by(Task.created_at.desc())
        .limit(1)
    )
    artifacts = (
        (await _load_artifacts(session, [latest_task.id])).get(latest_task.id, [])
        if latest_task is not None
        else []
    )
    return _to_item_read(item, latest_task, artifacts)


async def remove_item(
    session: AsyncSession,
    project: Project,
    item_id: UUID,
) -> None:
    if await has_active_run(session, project.id):
        raise ConflictError("Items cannot be removed while a run is active")

    item = await session.scalar(
        select(ProjectItem).where(
            ProjectItem.id == item_id,
            ProjectItem.project_id == project.id,
        )
    )
    if item is None:
        raise NotFoundError("Project item not found")

    await session.delete(item)
    await session.commit()
