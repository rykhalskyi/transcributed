import asyncio
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

import aio_pika
import psycopg
import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from transcributed.config import get_settings
from transcributed.db import SessionLocal, engine
from transcributed.enums import TaskStatus
from transcributed.logging import configure_logging
from transcributed.messaging.topology import declare_topology
from transcributed.models import Artifact, ProjectItem, Task, TaskFrame
from transcributed.services.spec import resolve_input_path
from transcributed.services.status import refresh_run_status
from transcributed.worker.frames import (
    FfmpegFrameExtractor,
    FrameExtractionResult,
    FrameExtractor,
    NoFramesExtracted,
)
from transcributed.worker.transcriber import (
    FakeTranscriber,
    FasterWhisperTranscriber,
    PermanentTaskError,
    TaskCancelled,
    Transcriber,
)

settings = get_settings()
log = structlog.get_logger(__name__)

CANCEL_CHECK_CONNECT_TIMEOUT_SECONDS = 5
PROGRESS_CONNECT_TIMEOUT_SECONDS = 5

CONTENT_TYPES = {
    "vtt": "text/vtt; charset=utf-8",
    "json": "application/json",
    "txt": "text/plain; charset=utf-8",
}


class TaskDisposition(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NOOP = "noop"


@dataclass(frozen=True)
class TaskOutcome:
    disposition: TaskDisposition
    task_id: UUID | None = None
    run_id: UUID | None = None


def create_transcriber() -> Transcriber:
    if settings.worker_backend == "fake":
        return FakeTranscriber()
    if settings.worker_backend == "faster-whisper":
        return FasterWhisperTranscriber(
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
            model_dir=settings.whisper_model_dir,
            beam_size=settings.whisper_beam_size,
            vad_filter=settings.whisper_vad_filter,
            ffmpeg_binary=settings.ffmpeg_binary,
            local_files_only=settings.whisper_local_files_only,
            baked_model=settings.whisper_model,
        )
    raise ValueError(f"Unsupported worker backend: {settings.worker_backend}")


def create_frame_extractor() -> FrameExtractor:
    return FfmpegFrameExtractor(ffmpeg_binary=settings.ffmpeg_binary)


def sync_database_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


class CancellationCheck:
    def __init__(self, task_id: UUID, dsn: str) -> None:
        self.task_id = task_id
        self.dsn = dsn
        self._connection: psycopg.Connection[Any] | None = None

    def __call__(self) -> bool:
        try:
            if self._connection is None or self._connection.closed:
                self._connection = psycopg.connect(
                    self.dsn,
                    autocommit=True,
                    connect_timeout=CANCEL_CHECK_CONNECT_TIMEOUT_SECONDS,
                )
            row = self._connection.execute(
                "SELECT status FROM tasks WHERE id = %s",
                (self.task_id,),
            ).fetchone()
        except Exception:
            log.warning(
                "cancel_check_failed",
                task_id=str(self.task_id),
                exc_info=True,
            )
            self.close()
            return False
        return row is None or row[0] != TaskStatus.PROCESSING.value

    def close(self) -> None:
        connection = self._connection
        self._connection = None
        if connection is not None:
            try:
                connection.close()
            except Exception:
                log.warning(
                    "cancel_check_close_failed",
                    task_id=str(self.task_id),
                    exc_info=True,
                )

class ProgressReporter:
    def __init__(self, task_id: UUID, dsn: str) -> None:
        self.task_id = task_id
        self.dsn = dsn
        self._connection: psycopg.Connection[Any] | None = None
        self._last_percent = -1

    def __call__(self, percent: int) -> None:
        value = max(0, min(100, int(percent)))
        if value <= self._last_percent:
            return
        try:
            if self._connection is None or self._connection.closed:
                self._connection = psycopg.connect(
                    self.dsn,
                    autocommit=True,
                    connect_timeout=PROGRESS_CONNECT_TIMEOUT_SECONDS,
                )
            self._connection.execute(
                "UPDATE tasks SET progress = GREATEST(progress, %s), "
                "updated_at = now() WHERE id = %s",
                (value, self.task_id),
            )
        except Exception:
            log.warning(
                "progress_report_failed",
                task_id=str(self.task_id),
                progress=value,
                exc_info=True,
            )
            self.close()
            return
        self._last_percent = value

    def close(self) -> None:
        connection = self._connection
        self._connection = None
        if connection is not None:
            try:
                connection.close()
            except Exception:
                log.warning(
                    "progress_report_close_failed",
                    task_id=str(self.task_id),
                    exc_info=True,
                )


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


async def process_task(
    session: AsyncSession,
    task_id: UUID,
    transcriber: Transcriber | None = None,
    frame_extractor: FrameExtractor | None = None,
) -> TaskOutcome:
    task = await load_task(session, task_id)
    if task is None:
        log.warning("task_not_found", task_id=str(task_id))
        return TaskOutcome(TaskDisposition.NOOP)

    if task.status in (
        TaskStatus.SUCCEEDED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    ):
        log.info("task_already_terminal", task_id=str(task_id), status=task.status)
        return TaskOutcome(TaskDisposition.NOOP)

    if task.status == TaskStatus.PROCESSING:
        task.status = TaskStatus.FAILED
        task.error = "worker stopped before finishing the task"
        task.finished_at = datetime.now(UTC)
        await session.flush()
        await refresh_run_status(session, task.run_id)
        await session.commit()
        log.error("task_abandoned", task_id=str(task_id))
        return TaskOutcome(
            TaskDisposition.FAILED,
            task_id=task.id,
            run_id=task.run_id,
        )

    now = datetime.now(UTC)
    task.status = TaskStatus.PROCESSING
    task.started_at = now
    task.finished_at = None
    task.worker_pod = os.getenv("POD_NAME") or None
    task.worker_node = os.getenv("NODE_NAME") or None
    task.progress = 0
    task.frames_extracted = 0
    task.frames_skipped = 0
    task.error = None
    await session.flush()
    await refresh_run_status(session, task.run_id)
    await session.commit()

    log.info(
        "task_started",
        task_id=str(task.id),
        run_id=str(task.run_id),
        path=task.project_item.video.path,
    )

    try:
        resolved = resolve_input_path(
            task.project_item.video.path,
            settings.nas_input_root,
            settings.allowed_extensions,
        )
        kind = str(task.spec.get("kind") or "transcribe")
        cancel_check = CancellationCheck(
            task.id,
            sync_database_url(settings.database_url),
        )
        progress_reporter = ProgressReporter(
            task.id,
            sync_database_url(settings.database_url),
        )
        started = time.monotonic()
        files: dict[str, str] = {}
        frame_result: FrameExtractionResult | None = None
        worker: Transcriber | FrameExtractor
        worker_details: dict[str, Any] = {}

        if kind == "frames":
            extractor = frame_extractor or create_frame_extractor()
            worker = extractor

            def run_frame_extraction(
                input_path: Path,
                spec: dict[str, Any],
            ) -> FrameExtractionResult:
                try:
                    return extractor.extract(
                        input_path,
                        spec,
                        should_cancel=cancel_check,
                        on_progress=progress_reporter,
                    )
                finally:
                    cancel_check.close()
                    progress_reporter.close()

            frame_result = await asyncio.to_thread(
                run_frame_extraction,
                resolved.absolute_path,
                task.spec,
            )
            if not frame_result.frames:
                raise NoFramesExtracted(len(frame_result.skipped))
            worker_details = {"ffmpeg_binary": getattr(extractor, "ffmpeg_binary", None)}
        else:
            selected_transcriber = transcriber or create_transcriber()
            worker = selected_transcriber

            def run_transcription(
                input_path: Path,
                spec: dict[str, Any],
            ) -> dict[str, str]:
                try:
                    return selected_transcriber.transcribe(
                        input_path,
                        spec,
                        should_cancel=cancel_check,
                        on_progress=progress_reporter,
                    )
                finally:
                    cancel_check.close()
                    progress_reporter.close()

            files = await asyncio.to_thread(
                run_transcription,
                resolved.absolute_path,
                task.spec,
            )
            if isinstance(selected_transcriber, FasterWhisperTranscriber):
                worker_details = {
                    "device": selected_transcriber.device,
                    "compute_type": selected_transcriber.compute_type,
                    "beam_size": selected_transcriber.beam_size,
                    "vad_filter": selected_transcriber.vad_filter,
                    "local_files_only": selected_transcriber.local_files_only,
                }

        elapsed_seconds = round(time.monotonic() - started, 3)

        if kind == "frames":
            assert frame_result is not None
            requested = len(task.spec.get("timecodes") or [])
            manifest = {
                "task_id": str(task.id),
                "run_id": str(task.run_id),
                "project_id": str(task.run.project_id),
                "source_path": task.project_item.video.path,
                "kind": "frames",
                "spec": task.spec,
                "extractor": type(worker).__name__,
                "worker": worker_details,
                "worker_pod": task.worker_pod,
                "worker_node": task.worker_node,
                "requested": requested,
                "extracted": len(frame_result.frames),
                "skipped": frame_result.skipped,
                "frames": [
                    {
                        "index": frame.index,
                        "timecode": frame.timecode,
                        "seconds": frame.timecode_seconds,
                        "filename": frame.filename,
                        "width": frame.width,
                        "height": frame.height,
                        "size_bytes": len(frame.data),
                    }
                    for frame in frame_result.frames
                ],
                "progress_percent": 100,
                "elapsed_seconds": elapsed_seconds,
                "generated_at": datetime.now(UTC).isoformat(),
            }
            metadata = json.dumps(manifest, ensure_ascii=False, indent=2)
        else:
            metadata = json.dumps(
                {
                    "task_id": str(task.id),
                    "run_id": str(task.run_id),
                    "project_id": str(task.run.project_id),
                    "source_path": task.project_item.video.path,
                    "spec": task.spec,
                    "transcriber": type(worker).__name__,
                    "model": task.spec.get("model"),
                    "worker": worker_details,
                    "worker_pod": task.worker_pod,
                    "worker_node": task.worker_node,
                    "progress_percent": 100,
                    "elapsed_seconds": elapsed_seconds,
                    "generated_at": datetime.now(UTC).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            )

        locked_status = await session.scalar(
            select(Task.status).where(Task.id == task.id).with_for_update()
        )
        if locked_status != TaskStatus.PROCESSING:
            current_task_id = task.id
            current_run_id = task.run_id
            await session.rollback()
            if locked_status == TaskStatus.CANCELLED:
                log.info("task_cancelled", task_id=str(current_task_id))
                return TaskOutcome(
                    TaskDisposition.CANCELLED,
                    task_id=current_task_id,
                    run_id=current_run_id,
                )
            return TaskOutcome(TaskDisposition.NOOP)

        await session.execute(delete(Artifact).where(Artifact.task_id == task.id))
        if kind == "frames":
            assert frame_result is not None
            await session.execute(
                delete(TaskFrame).where(TaskFrame.task_id == task.id)
            )
            session.add_all(
                [
                    TaskFrame(
                        task_id=task.id,
                        index=frame.index,
                        timecode_seconds=float(frame.timecode_seconds),
                        timecode=frame.timecode,
                        filename=frame.filename,
                        content_type="image/png",
                        width=frame.width,
                        height=frame.height,
                        size_bytes=len(frame.data),
                        sha256=hashlib.sha256(frame.data).hexdigest(),
                        data=frame.data,
                    )
                    for frame in frame_result.frames
                ]
            )
            source_stem = Path(task.project_item.video.path).stem or "video"
            artifacts = [
                Artifact(
                    task_id=task.id,
                    format="manifest",
                    filename="frames.json",
                    content_type="application/json",
                    content=metadata,
                    size_bytes=len(metadata.encode("utf-8")),
                ),
                Artifact(
                    task_id=task.id,
                    format="zip",
                    filename=f"{source_stem}-frames.zip",
                    content_type="application/zip",
                    content=None,
                    size_bytes=(
                        sum(len(frame.data) for frame in frame_result.frames)
                        + len(metadata.encode("utf-8"))
                    ),
                ),
            ]
            task.frames_extracted = len(frame_result.frames)
            task.frames_skipped = len(frame_result.skipped)
        else:
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
        task.progress = 100
        task.finished_at = datetime.now(UTC)
        task.error = None
        await session.flush()
        await refresh_run_status(session, task.run_id)
        await session.commit()

        log.info("task_succeeded", task_id=str(task.id), run_id=str(task.run_id))
        return TaskOutcome(
            TaskDisposition.SUCCEEDED,
            task_id=task.id,
            run_id=task.run_id,
        )
    except TaskCancelled:
        await session.rollback()
        task = await session.get(Task, task_id, populate_existing=True)
        if task is not None:
            await refresh_run_status(session, task.run_id)
            await session.commit()
        log.info(
            "task_cancelled",
            task_id=str(task_id),
            run_id=str(task.run_id) if task is not None else None,
        )
        return TaskOutcome(
            TaskDisposition.CANCELLED,
            task_id=task.id if task is not None else task_id,
            run_id=task.run_id if task is not None else None,
        )
    except Exception as exc:
        await session.rollback()
        log.exception("task_failed", task_id=str(task_id), run_id=str(task.run_id))
        task = await session.scalar(
            select(Task)
            .where(Task.id == task_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if task is None:
            return TaskOutcome(TaskDisposition.NOOP)
        if task.status in (
            TaskStatus.SUCCEEDED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        ):
            status = task.status
            run_id = task.run_id
            await session.rollback()
            if status == TaskStatus.CANCELLED:
                log.info("task_cancelled", task_id=str(task_id))
                return TaskOutcome(
                    TaskDisposition.CANCELLED,
                    task_id=task_id,
                    run_id=run_id,
                )
            return TaskOutcome(TaskDisposition.NOOP)

        if isinstance(exc, NoFramesExtracted):
            task.frames_extracted = 0
            task.frames_skipped = exc.skipped
        task.error = str(exc)[:4000]
        if isinstance(exc, PermanentTaskError):
            log.error("task_permanent_failure", task_id=str(task_id), error=task.error)
        task.status = TaskStatus.FAILED
        task.finished_at = datetime.now(UTC)
        await session.flush()
        await refresh_run_status(session, task.run_id)
        await session.commit()
        return TaskOutcome(
            TaskDisposition.FAILED,
            task_id=task.id,
            run_id=task.run_id,
        )


async def run_once(queue_name: str | None = None) -> int:
    configure_logging(settings.log_level)
    if not settings.rabbitmq_enabled:
        log.warning("worker_rabbitmq_disabled")
        return 0

    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    async with connection:
        channel = await connection.channel(publisher_confirms=True)
        await channel.set_qos(prefetch_count=1)
        topology = await declare_topology(
            channel,
            settings.rabbitmq_exchange,
            settings.rabbitmq_jobs_queue,
            settings.rabbitmq_frames_queue,
        )
        selected_queue = (
            topology.frames_queue
            if queue_name == settings.rabbitmq_frames_queue
            else topology.jobs_queue
        )
        message = await selected_queue.get(no_ack=False, fail=False)
        if message is None:
            log.info("worker_no_task_available")
            await engine.dispose()
            return 0

        try:
            payload = json.loads(message.body)
            task_id = UUID(payload["task_id"])
            run_id = UUID(payload["run_id"])
        except (KeyError, TypeError, ValueError):
            log.exception("worker_invalid_message")
            await message.reject(requeue=False)
            await engine.dispose()
            return 0

        try:
            async with SessionLocal() as session:
                outcome = await process_task(session, task_id)
        except Exception:
            log.exception(
                "worker_unhandled_error",
                task_id=str(task_id),
                run_id=str(run_id),
            )
            raise

        try:
            if outcome.disposition == TaskDisposition.FAILED:
                await message.reject(requeue=False)
            else:
                await message.ack()
        except Exception:
            log.warning(
                "worker_message_settle_failed",
                task_id=str(task_id),
                disposition=outcome.disposition,
                exc_info=True,
            )

    await engine.dispose()
    return 0


def _run(worker: Any) -> None:
    try:
        raise SystemExit(asyncio.run(worker()))
    except SystemExit:
        raise
    except Exception:
        configure_logging(settings.log_level)
        log.exception("worker_crashed")
        sys.exit(1)


def main() -> None:
    _run(run_once)


def frame_main() -> None:
    _run(lambda: run_once(settings.rabbitmq_frames_queue))
