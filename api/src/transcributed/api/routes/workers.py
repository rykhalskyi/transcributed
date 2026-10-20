from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from transcributed.db import get_session
from transcributed.schemas import WorkersResponse
from transcributed.services import workers as worker_service

router = APIRouter(prefix="/workers", tags=["workers"])


@router.get("", response_model=WorkersResponse)
async def list_workers(
    project_id: Annotated[UUID | None, Query()] = None,
    run_id: Annotated[UUID | None, Query()] = None,
    session: AsyncSession = Depends(get_session),
) -> WorkersResponse:
    return await worker_service.list_workers(
        session,
        project_id=project_id,
        run_id=run_id,
    )
