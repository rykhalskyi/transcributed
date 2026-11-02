from __future__ import annotations

import base64
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import structlog

from transcributed.services.frames import frame_filename, parse_png_dimensions
from transcributed.worker.transcriber import PermanentTaskError, TaskCancelled

log = structlog.get_logger(__name__)

FAKE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


@dataclass(frozen=True)
class ExtractedFrame:
    index: int
    timecode_seconds: int
    timecode: str
    filename: str
    data: bytes
    width: int
    height: int


@dataclass(frozen=True)
class FrameExtractionResult:
    frames: list[ExtractedFrame]
    skipped: list[str]


class NoFramesExtracted(PermanentTaskError):
    def __init__(self, skipped: int) -> None:
        super().__init__("no frames extracted")
        self.skipped = skipped


class FrameExtractor(Protocol):
    def extract(
        self,
        input_path: Path,
        spec: dict[str, Any],
        *,
        should_cancel: Callable[[], bool] | None = None,
        on_progress: Callable[[int], None] | None = None,
    ) -> FrameExtractionResult: ...


def _timecodes(spec: dict[str, Any]) -> list[dict[str, Any]]:
    values = spec.get("timecodes")
    if not isinstance(values, list) or not values:
        raise ValueError("frame task spec has no timecodes")
    return [value for value in values if isinstance(value, dict)]


class FfmpegFrameExtractor:
    def __init__(self, ffmpeg_binary: str = "ffmpeg") -> None:
        self.ffmpeg_binary = ffmpeg_binary

    def _extract_one(self, input_path: Path, seconds: int) -> bytes | None:
        command = [
            self.ffmpeg_binary,
            "-nostdin",
            "-v",
            "error",
            "-ss",
            str(seconds),
            "-i",
            str(input_path),
            "-frames:v",
            "1",
            "-an",
            "-sn",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "-",
        ]
        try:
            result = subprocess.run(command, capture_output=True)
        except OSError:
            log.exception("frame_ffmpeg_failed", path=str(input_path), seconds=seconds)
            return None
        if result.returncode != 0 or not result.stdout:
            log.debug(
                "frame_skipped",
                path=str(input_path),
                seconds=seconds,
                error=result.stderr.decode("utf-8", "replace").strip()[:200],
            )
            return None
        return result.stdout

    def extract(
        self,
        input_path: Path,
        spec: dict[str, Any],
        *,
        should_cancel: Callable[[], bool] | None = None,
        on_progress: Callable[[int], None] | None = None,
    ) -> FrameExtractionResult:
        started = time.monotonic()
        timecodes = _timecodes(spec)
        total = len(timecodes)
        frames: list[ExtractedFrame] = []
        skipped: list[str] = []
        if on_progress is not None:
            on_progress(0)

        for position, item in enumerate(timecodes, start=1):
            if should_cancel is not None and should_cancel():
                raise TaskCancelled("cancelled by user")

            seconds = int(item.get("seconds", 0))
            timecode = str(item.get("timecode") or "")
            data = self._extract_one(input_path, seconds)
            if data is None:
                skipped.append(timecode)
            else:
                width, height = parse_png_dimensions(data)
                frames.append(
                    ExtractedFrame(
                        index=position,
                        timecode_seconds=seconds,
                        timecode=timecode,
                        filename=frame_filename(position, timecode),
                        data=data,
                        width=width,
                        height=height,
                    )
                )

            if on_progress is not None:
                on_progress(int(position / total * 99))

        log.info(
            "frame_extraction_finished",
            path=str(input_path),
            requested=total,
            extracted=len(frames),
            skipped=len(skipped),
            elapsed_seconds=round(time.monotonic() - started, 1),
        )
        return FrameExtractionResult(frames=frames, skipped=skipped)


class FakeFrameExtractor:
    def extract(
        self,
        input_path: Path,
        spec: dict[str, Any],
        *,
        should_cancel: Callable[[], bool] | None = None,
        on_progress: Callable[[int], None] | None = None,
    ) -> FrameExtractionResult:
        timecodes = _timecodes(spec)
        total = len(timecodes)
        frames: list[ExtractedFrame] = []
        if on_progress is not None:
            on_progress(0)
        for position, item in enumerate(timecodes, start=1):
            if should_cancel is not None and should_cancel():
                raise TaskCancelled("cancelled by user")
            seconds = int(item.get("seconds", 0))
            timecode = str(item.get("timecode") or "")
            width, height = parse_png_dimensions(FAKE_PNG)
            frames.append(
                ExtractedFrame(
                    index=position,
                    timecode_seconds=seconds,
                    timecode=timecode,
                    filename=frame_filename(position, timecode),
                    data=FAKE_PNG,
                    width=width,
                    height=height,
                )
            )
            if on_progress is not None:
                on_progress(int(position / total * 99))
        return FrameExtractionResult(frames=frames, skipped=[])
