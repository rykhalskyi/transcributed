from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from transcributed.db import get_session
from transcributed.errors import NotFoundError
from transcributed.models import TaskFrame
from transcributed.schemas import TaskRead
from transcributed.services import runs as run_service
from transcributed.services.frames import build_frames_zip

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> TaskRead:
    task = await run_service.get_task(session, task_id)
    return TaskRead.model_validate(task)


@router.post("/{task_id}/cancel", response_model=TaskRead)
async def cancel_task(
    task_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> TaskRead:
    task = await run_service.cancel_task(session, task_id)
    return TaskRead.model_validate(task)


@router.get("/{task_id}/files/{file_format}")
async def download_file(
    task_id: UUID,
    file_format: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    task = await run_service.get_task(session, task_id)
    artifact = next(
        (item for item in task.artifacts if item.format == file_format),
        None,
    )
    if artifact is None:
        raise NotFoundError("Artifact not found")

    content: bytes | str | None = artifact.content
    if artifact.format == "zip" and content is None:
        frames = (
            await session.scalars(
                select(TaskFrame)
                .where(TaskFrame.task_id == task.id)
                .order_by(TaskFrame.index)
            )
        ).all()
        manifest = next(
            (
                item.content
                for item in task.artifacts
                if item.format == "manifest" and item.content is not None
            ),
            "{}",
        )
        content = build_frames_zip(frames, manifest)

    if content is None:
        raise NotFoundError("Artifact not found")
    return Response(
        content=content,
        media_type=artifact.content_type,
        headers={"Content-Disposition": f'attachment; filename="{artifact.filename}"'},
    )
