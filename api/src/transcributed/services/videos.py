from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from transcributed.models import Video
from transcributed.services.spec import ResolvedInput


async def get_or_create_video(session: AsyncSession, resolved: ResolvedInput) -> Video:
    video_id = await session.scalar(
        pg_insert(Video)
        .values(
            path=resolved.relative_path,
            size_bytes=resolved.size_bytes,
            mtime=resolved.mtime,
        )
        .on_conflict_do_nothing(constraint="uq_videos_path_size_mtime")
        .returning(Video.id)
    )
    if video_id is not None:
        video = await session.get(Video, video_id)
        if video is not None:
            return video

    video = await session.scalar(
        select(Video).where(
            Video.path == resolved.relative_path,
            Video.size_bytes == resolved.size_bytes,
            Video.mtime == resolved.mtime,
        )
    )
    if video is None:
        raise RuntimeError("Failed to create or load video")
    return video
