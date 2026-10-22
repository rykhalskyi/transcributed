import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from transcributed.worker.transcriber import (
    FakeTranscriber,
    FasterWhisperTranscriber,
    PermanentTaskError,
    TaskCancelled,
    TranscriptSegment,
    language_code,
    render_json,
    render_txt,
    render_vtt,
)

SEGMENTS = [
    TranscriptSegment(start=0.0, end=1.5, text="Hello"),
    TranscriptSegment(start=3661.25, end=3662.5, text="World"),
]


def test_language_code_maps_auto_to_none() -> None:
    assert language_code("auto") is None
    assert language_code(None) is None
    assert language_code("de") == "de"


def test_render_txt_joins_segments() -> None:
    assert render_txt(SEGMENTS) == "Hello\nWorld\n"
    assert render_txt([]) == ""


def test_render_txt_can_include_timestamps() -> None:
    assert render_txt(SEGMENTS, timestamps=True) == (
        "[00:00:00.000 --> 00:00:01.500] Hello\n"
        "[01:01:01.250 --> 01:01:02.500] World\n"
    )
    assert render_txt([], timestamps=True) == ""


def test_render_vtt_formats_timestamps() -> None:
    result = render_vtt(SEGMENTS)

    assert result.startswith("WEBVTT\n\n00:00:00.000 --> 00:00:01.500\nHello\n")
    assert "01:01:01.250 --> 01:01:02.500\nWorld\n" in result


def test_render_json_has_segments_without_word_timestamps() -> None:
    payload = json.loads(render_json(SEGMENTS, "en"))

    assert payload["language"] == "en"
    assert payload["text"] == "Hello\nWorld"
    assert payload["segments"] == [
        {"start": 0.0, "end": 1.5, "text": "Hello"},
        {"start": 3661.25, "end": 3662.5, "text": "World"},
    ]
    assert "words" not in payload["segments"][0]


class FakeModel:
    def __init__(self, language: str | None = "ru") -> None:
        self.audio: Any = None
        self.kwargs: dict[str, Any] = {}
        self.language = language

    def transcribe(self, audio: Any, **kwargs: Any) -> tuple[Iterator[Any], Any]:
        self.audio = audio
        self.kwargs = kwargs
        segments = [SimpleNamespace(start=0.0, end=1.25, text=" hello ")]
        return iter(segments), SimpleNamespace(language=self.language)


def test_faster_whisper_transcriber_maps_spec_and_renders(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = FakeModel()
    transcriber = FasterWhisperTranscriber()
    monkeypatch.setattr(transcriber, "_load_model", lambda _: model)
    monkeypatch.setattr(transcriber, "_decode_audio", lambda _: [0.0])

    files = transcriber.transcribe(
        tmp_path / "lecture.mp4",
        {
            "model": "small",
            "language": "auto",
            "output_formats": ["txt", "vtt", "json"],
        },
    )

    assert model.audio == [0.0]
    assert model.kwargs["language"] is None
    assert model.kwargs["vad_filter"] is True
    assert model.kwargs["word_timestamps"] is False
    assert files["txt"] == "hello\n"
    assert files["vtt"].startswith("WEBVTT\n\n00:00:00.000 --> 00:00:01.250\nhello\n")
    assert json.loads(files["json"])["text"] == "hello"
    assert json.loads(files["json"])["language"] == "ru"


def test_faster_whisper_transcriber_renders_timestamped_txt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcriber = FasterWhisperTranscriber()
    monkeypatch.setattr(transcriber, "_load_model", lambda _: FakeModel())
    monkeypatch.setattr(transcriber, "_decode_audio", lambda _: [0.0])

    files = transcriber.transcribe(
        tmp_path / "lecture.mp4",
        {
            "model": "small",
            "language": "en",
            "output_formats": ["txt"],
            "txt_timestamps": True,
        },
    )

    assert files["txt"] == "[00:00:00.000 --> 00:00:01.250] hello\n"


def test_faster_whisper_transcriber_writes_only_requested_formats(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcriber = FasterWhisperTranscriber()
    monkeypatch.setattr(transcriber, "_load_model", lambda _: FakeModel())
    monkeypatch.setattr(transcriber, "_decode_audio", lambda _: [0.0])

    files = transcriber.transcribe(
        tmp_path / "lecture.mp4",
        {"model": "small", "language": "en", "output_formats": ["vtt"]},
    )

    assert set(files) == {"vtt"}


def test_faster_whisper_transcriber_falls_back_to_requested_language(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcriber = FasterWhisperTranscriber()
    monkeypatch.setattr(transcriber, "_load_model", lambda _: FakeModel(language=None))
    monkeypatch.setattr(transcriber, "_decode_audio", lambda _: [0.0])

    files = transcriber.transcribe(
        tmp_path / "lecture.mp4",
        {"model": "small", "language": "en", "output_formats": ["json"]},
    )

    assert json.loads(files["json"])["language"] == "en"


def test_faster_whisper_transcriber_uses_worker_vad_setting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = FakeModel()
    transcriber = FasterWhisperTranscriber(vad_filter=False)
    monkeypatch.setattr(transcriber, "_load_model", lambda _: model)
    monkeypatch.setattr(transcriber, "_decode_audio", lambda _: [0.0])

    transcriber.transcribe(
        tmp_path / "lecture.mp4",
        {"model": "small", "language": "en", "output_formats": ["txt"]},
    )

    assert model.kwargs["vad_filter"] is False


def test_fake_transcriber_renders_timestamped_txt(tmp_path: Path) -> None:
    files = FakeTranscriber().transcribe(
        tmp_path / "lecture.mp4",
        {"output_formats": ["txt"], "txt_timestamps": True},
    )

    assert files["txt"].startswith(
        "[00:00:00.000 --> 00:00:05.000] [Fake transcript"
    )


def test_faster_whisper_transcriber_rejects_model_missing_from_image(
    tmp_path: Path,
) -> None:
    transcriber = FasterWhisperTranscriber(
        local_files_only=True,
        baked_model="small",
    )

    with pytest.raises(PermanentTaskError, match="tiny"):
        transcriber.transcribe(
            tmp_path / "lecture.mp4",
            {"model": "tiny", "language": "en"},
        )


def test_ffmpeg_command_requests_16k_mono_pcm(tmp_path: Path) -> None:
    transcriber = FasterWhisperTranscriber(ffmpeg_binary="/usr/bin/ffmpeg")

    command = transcriber._ffmpeg_command(tmp_path / "lecture.avi")

    assert command[0] == "/usr/bin/ffmpeg"
    assert command[-1] == "-"
    assert command[command.index("-ar") + 1] == "16000"
    assert command[command.index("-ac") + 1] == "1"
    assert "pcm_s16le" in command


def test_decode_audio_reports_ffmpeg_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stderr=b"bad input", stdout=b""),
    )
    transcriber = FasterWhisperTranscriber()

    with pytest.raises(RuntimeError, match="ffmpeg failed to decode"):
        transcriber._decode_audio(tmp_path / "lecture.avi")


def test_transcriber_stops_when_cancelled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcriber = FasterWhisperTranscriber()
    monkeypatch.setattr(transcriber, "_load_model", lambda _: FakeModel())
    monkeypatch.setattr(transcriber, "_decode_audio", lambda _: [0.0])

    with pytest.raises(TaskCancelled):
        transcriber.transcribe(
            tmp_path / "lecture.mp4",
            {"model": "small", "language": "en"},
            should_cancel=lambda: True,
        )
