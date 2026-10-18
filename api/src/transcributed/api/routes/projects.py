from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from transcributed.api.deps import get_publisher
from transcributed.db import get_session
from transcributed.messaging.publisher import TaskPublisher
from transcributed.schemas import (
    ProjectCreate,
    ProjectItemRead,
    ProjectItemsAddRequest,
    ProjectItemsAddResponse,
    ProjectRead,
    ProjectUpdate,
    RunRead,
    StartProjectResponse,
)
from transcributed.services import projects as project_service
from transcributed.services import runs as run_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    session: AsyncSession = Depends(get_session),
) -> ProjectRead:
    project = await project_service.create_project(session, payload)
    return ProjectRead.model_validate(project)


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    session: AsyncSession = Depends(get_session),
) -> list[ProjectRead]:
    projects = await project_service.list_projects(session)
    return [ProjectRead.model_validate(project) for project in projects]


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ProjectRead:
    project = await project_service.get_project(session, project_id)
    return ProjectRead.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    session: AsyncSession = Depends(get_session),
) -> ProjectRead:
    project = await project_service.get_project(session, project_id)
    project = await project_service.update_project(session, project, payload)
    return ProjectRead.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    project = await project_service.get_project(session, project_id)
    await project_service.delete_project(session, project)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{project_id}/items",
    response_model=ProjectItemsAddResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_project_items(
    project_id: UUID,
    payload: ProjectItemsAddRequest,
    session: AsyncSession = Depends(get_session),
) -> ProjectItemsAddResponse:
    project = await project_service.get_project(session, project_id)
    return await project_service.add_items(session, project, payload)


@router.get("/{project_id}/items", response_model=list[ProjectItemRead])
async def list_project_items(
    project_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> list[ProjectItemRead]:
    await project_service.get_project(session, project_id)
    items = await project_service.list_project_items(session, project_id)
    return list(items)


@router.delete(
    "/{project_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_project_item(
    project_id: UUID,
    item_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    project = await project_service.get_project(session, project_id)
    await project_service.remove_item(session, project, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{project_id}/start",
    response_model=StartProjectResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_project(
    project_id: UUID,
    session: AsyncSession = Depends(get_session),
    publisher: TaskPublisher = Depends(get_publisher),
) -> StartProjectResponse:
    project = await project_service.get_project(session, project_id)
    run, tasks, enqueued = await run_service.start_project(session, project, publisher)
    return StartProjectResponse(
        run=RunRead.model_validate(run),
        task_ids=[task.id for task in tasks],
        enqueued=enqueued,
        not_enqueued=len(tasks) - enqueued,
    )


@router.get("/{project_id}/runs", response_model=list[RunRead])
async def list_project_runs(
    project_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> list[RunRead]:
    await project_service.get_project(session, project_id)
    runs = await run_service.list_project_runs(session, project_id)
    return [RunRead.model_validate(run) for run in runs]
