from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from transcributed.db import get_session
from transcributed.schemas import RunDetail
from transcributed.services import runs as run_service

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> RunDetail:
    run = await run_service.get_run(session, run_id)
    return RunDetail.model_validate(run)
