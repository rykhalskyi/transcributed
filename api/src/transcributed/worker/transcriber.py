import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import structlog

CANCEL_CHECK_INTERVAL_SECONDS = 30.0
PROGRESS_INTERVAL_SECONDS = 60.0
SAMPLE_RATE = 16000

log = structlog.get_logger(__name__)


class TaskCancelled(Exception):
    pass


class Transcriber(Protocol):
    def transcribe(
        self,
        input_path: Path,
        spec: dict[str, Any],
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> dict[str, str]: ...


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


def _timestamp(seconds: float) -> str:
    total_milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"


def render_txt(segments: Sequence[TranscriptSegment]) -> str:
    lines = [segment.text for segment in segments]
    return "\n".join(lines) + ("\n" if lines else "")


def render_vtt(segments: Sequence[TranscriptSegment]) -> str:
    lines = ["WEBVTT", ""]
    for segment in segments:
        lines.extend(
            [
                f"{_timestamp(segment.start)} --> {_timestamp(segment.end)}",
                segment.text,
                "",
            ]
        )
    return "\n".join(lines)


def render_json(
    segments: Sequence[TranscriptSegment],
    language: str | None,
) -> str:
    payload = {
        "language": language,
        "text": "\n".join(segment.text for segment in segments),
        "segments": [
            {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
            }
            for segment in segments
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def language_code(language: Any) -> str | None:
    if not language or language == "auto":
        return None
    return str(language)


_MODEL_CACHE: dict[tuple[str, str, str, str | None, bool], Any] = {}


class FasterWhisperTranscriber:
    def __init__(
        self,
        *,
        device: str = "cpu",
        compute_type: str = "int8",
        model_dir: Path | None = None,
        beam_size: int = 5,
        vad_filter: bool = True,
        ffmpeg_binary: str = "ffmpeg",
        local_files_only: bool = False,
    ) -> None:
        self.device = device
        self.compute_type = compute_type
        self.model_dir = model_dir
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self.ffmpeg_binary = ffmpeg_binary
        self.local_files_only = local_files_only

    def _ffmpeg_command(self, input_path: Path) -> list[str]:
        return [
            self.ffmpeg_binary,
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(input_path),
            "-vn",
            "-map",
            "0:a:0",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-",
        ]

    def _decode_audio(self, input_path: Path) -> Any:
        import subprocess

        import numpy as np

        try:
            result = subprocess.run(
                self._ffmpeg_command(input_path),
                capture_output=True,
            )
        except OSError as exc:
            raise RuntimeError(f"Failed to run {self.ffmpeg_binary}: {exc}") from exc

        if result.returncode != 0:
            message = result.stderr.decode("utf-8", "replace").strip()[:500]
            raise RuntimeError(f"ffmpeg failed to decode {input_path.name}: {message}")
        if not result.stdout:
            raise RuntimeError(f"ffmpeg produced no audio for {input_path.name}")

        return np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0

    def _load_model(self, model_name: str) -> Any:
        key = (
            model_name,
            self.device,
            self.compute_type,
            str(self.model_dir) if self.model_dir is not None else None,
            self.local_files_only,
        )
        model = _MODEL_CACHE.get(key)
        if model is None:
            from faster_whisper import WhisperModel

            kwargs: dict[str, Any] = {
                "device": self.device,
                "compute_type": self.compute_type,
                "local_files_only": self.local_files_only,
            }
            if self.model_dir is not None:
                kwargs["download_root"] = str(self.model_dir)
            model = WhisperModel(model_name, **kwargs)
            _MODEL_CACHE[key] = model
            log.info(
                "model_loaded",
                model=model_name,
                device=self.device,
                compute_type=self.compute_type,
                local_files_only=self.local_files_only,
            )
        return model

    def transcribe(
        self,
        input_path: Path,
        spec: dict[str, Any],
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> dict[str, str]:
        started = time.monotonic()
        model_name = str(spec.get("model") or "small")
        model = self._load_model(model_name)
        audio = self._decode_audio(input_path)
        duration_seconds = len(audio) / SAMPLE_RATE
        log.info(
            "audio_decoded",
            path=str(input_path),
            duration_seconds=round(duration_seconds, 1),
            decode_seconds=round(time.monotonic() - started, 1),
        )

        segments_iter, _info = model.transcribe(
            audio,
            language=language_code(spec.get("language")),
            beam_size=self.beam_size,
            vad_filter=bool(spec.get("vad_filter", self.vad_filter)),
            word_timestamps=False,
        )
        segments: list[TranscriptSegment] = []
        next_cancel_check = 0.0
        next_progress = 0.0
        for segment in segments_iter:
            if should_cancel is not None and segment.end >= next_cancel_check:
                if should_cancel():
                    raise TaskCancelled("cancelled by user")
                next_cancel_check = segment.end + CANCEL_CHECK_INTERVAL_SECONDS
            if segment.end >= next_progress:
                log.info(
                    "transcription_progress",
                    path=str(input_path),
                    audio_seconds=round(float(segment.end), 1),
                    elapsed_seconds=round(time.monotonic() - started, 1),
                    text=str(segment.text).strip()[:200],
                )
                next_progress = segment.end + PROGRESS_INTERVAL_SECONDS
            segments.append(
                TranscriptSegment(
                    start=float(segment.start),
                    end=float(segment.end),
                    text=str(segment.text).strip(),
                )
            )

        log.info(
            "transcription_finished",
            path=str(input_path),
            audio_seconds=round(duration_seconds, 1),
            segments=len(segments),
            elapsed_seconds=round(time.monotonic() - started, 1),
        )

        formats = set(spec.get("output_formats") or ["txt"])
        files: dict[str, str] = {}
        if "vtt" in formats:
            files["vtt"] = render_vtt(segments)
        if "json" in formats:
            files["json"] = render_json(segments, spec.get("language"))
        if "txt" in formats:
            files["txt"] = render_txt(segments)
        return files


class FakeTranscriber:
    def transcribe(
        self,
        input_path: Path,
        spec: dict[str, Any],
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> dict[str, str]:
        text = f"[Fake transcript for {input_path.name}]"
        formats = set(spec.get("output_formats") or ["txt"])
        files: dict[str, str] = {}

        if "vtt" in formats:
            files["vtt"] = f"WEBVTT\n\n00:00:00.000 --> 00:00:05.000\n{text}\n"

        if "json" in formats:
            files["json"] = json.dumps(
                {
                    "language": spec.get("language"),
                    "text": text,
                    "segments": [{"start": 0.0, "end": 5.0, "text": text}],
                },
                ensure_ascii=False,
                indent=2,
            )

        if "txt" in formats:
            files["txt"] = f"{text}\n"

        return files
