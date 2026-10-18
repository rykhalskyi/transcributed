import asyncio
import json
import sys
from datetime import UTC, datetime
from uuid import UUID

import aio_pika
import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from transcributed.config import get_settings
from transcributed.db import SessionLocal, engine
from transcributed.enums import TaskStatus
from transcributed.logging import configure_logging
from transcributed.messaging.topology import declare_topology
from transcributed.models import Artifact, ProjectItem, Task
from transcributed.services.status import refresh_run_status
from transcributed.worker.transcriber import FakeTranscriber

settings = get_settings()
log = structlog.get_logger(__name__)

CONTENT_TYPES = {
    "vtt": "text/vtt; charset=utf-8",
    "json": "application/json",
    "txt": "text/plain; charset=utf-8",
}


async def load_task(session: AsyncSession, task_id: UUID) -> Task | None:
    return await session.scalar(
        select(Task)
        .where(Task.id == task_id)
        .options(
            selectinload(Task.project_item).selectinload(ProjectItem.video),
            selectinload(Task.run),
            selectinload(Task.artifacts),
        )
    )


async def process_task(session: AsyncSession, task_id: UUID) -> None:
    task = await load_task(session, task_id)
    if task is None:
        log.warning("task_not_found", task_id=str(task_id))
        return

    if task.status in (TaskStatus.SUCCEEDED, TaskStatus.FAILED):
        log.info("task_already_terminal", task_id=str(task_id), status=task.status)
        return

    if task.attempts >= task.max_attempts:
        task.status = TaskStatus.FAILED
        task.error = "max attempts exceeded"
        task.finished_at = datetime.now(UTC)
        await session.flush()
        await refresh_run_status(session, task.run_id)
        await session.commit()
        log.error("task_max_attempts", task_id=str(task_id))
        return

    now = datetime.now(UTC)
    task.status = TaskStatus.PROCESSING
    task.attempts += 1
    task.started_at = now
    task.finished_at = None
    task.error = None
    await session.flush()
    await refresh_run_status(session, task.run_id)
    await session.commit()

    log.info(
        "task_started",
        task_id=str(task.id),
        run_id=str(task.run_id),
        attempt=task.attempts,
        path=task.project_item.video.path,
    )

    try:
        from transcributed.services.spec import resolve_input_path

        resolved = resolve_input_path(
            task.project_item.video.path,
            settings.nas_input_root,
            settings.allowed_extensions,
        )

        files = FakeTranscriber().transcribe(resolved.absolute_path, task.spec)

        metadata = json.dumps(
            {
                "task_id": str(task.id),
                "run_id": str(task.run_id),
                "project_id": str(task.run.project_id),
                "source_path": task.project_item.video.path,
                "spec": task.spec,
                "transcriber": "fake",
                "generated_at": datetime.now(UTC).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        )

        await session.execute(delete(Artifact).where(Artifact.task_id == task.id))
        artifacts = [
            Artifact(
                task_id=task.id,
                format=file_format,
                filename=f"transcript.{file_format}",
                content_type=CONTENT_TYPES[file_format],
                content=content,
                size_bytes=len(content.encode("utf-8")),
            )
            for file_format, content in files.items()
        ]
        artifacts.append(
            Artifact(
                task_id=task.id,
                format="metadata",
                filename="metadata.json",
                content_type="application/json",
                content=metadata,
                size_bytes=len(metadata.encode("utf-8")),
            )
        )
        session.add_all(artifacts)

        task.status = TaskStatus.SUCCEEDED
        task.finished_at = datetime.now(UTC)
        task.error = None
        await session.flush()
        await refresh_run_status(session, task.run_id)
        await session.commit()

        log.info("task_succeeded", task_id=str(task.id), run_id=str(task.run_id))
    except Exception as exc:
        await session.rollback()
        log.exception("task_failed", task_id=str(task.id), run_id=str(task.run_id))
        task = await session.get(Task, task_id)
        if task is not None and task.status != TaskStatus.SUCCEEDED:
            task.status = TaskStatus.FAILED
            task.error = str(exc)[:4000]
            task.finished_at = datetime.now(UTC)
            await session.flush()
            await refresh_run_status(session, task.run_id)
            await session.commit()


async def run_once() -> int:
    configure_logging(settings.log_level)
    if not settings.rabbitmq_enabled:
        log.warning("worker_rabbitmq_disabled")
        return 0

    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        topology = await declare_topology(
            channel,
            settings.rabbitmq_exchange,
            settings.rabbitmq_jobs_queue,
        )
        message = await topology.jobs_queue.get(no_ack=False, fail=False)
        if message is None:
            log.info("worker_no_task_available")
            await engine.dispose()
            return 0

        async with message.process(requeue=True):
            payload = json.loads(message.body)
            task_id = UUID(payload["task_id"])
            async with SessionLocal() as session:
                await process_task(session, task_id)

    await engine.dispose()
    return 0


def main() -> None:
    try:
        raise SystemExit(asyncio.run(run_once()))
    except SystemExit:
        raise
    except Exception:
        configure_logging(settings.log_level)
        log.exception("worker_crashed")
        sys.exit(1)
