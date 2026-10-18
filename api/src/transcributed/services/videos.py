from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from transcributed.models import Video
from transcributed.services.spec import ResolvedInput


async def get_or_create_video(session: AsyncSession, resolved: ResolvedInput) -> Video:
    video = await session.scalar(
        select(Video).where(
            Video.path == resolved.relative_path,
            Video.size_bytes == resolved.size_bytes,
            Video.mtime == resolved.mtime,
        )
    )
    if video is not None:
        return video

    video = Video(
        path=resolved.relative_path,
        size_bytes=resolved.size_bytes,
        mtime=resolved.mtime,
    )
    session.add(video)
    await session.flush()
    return video
