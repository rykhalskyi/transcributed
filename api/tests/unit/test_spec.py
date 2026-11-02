from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from transcributed.errors import ValidationError
from transcributed.schemas import ProjectDefaults
from transcributed.services.spec import (
    build_effective_spec,
    resolve_input_path,
    source_matches,
    spec_hash,
)


def test_resolve_input_path_rejects_absolute(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        resolve_input_path("/etc/passwd", tmp_path, (".mp4",))


def test_resolve_input_path_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        resolve_input_path("../outside.mp4", tmp_path, (".mp4",))


def test_resolve_input_path_rejects_missing(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        resolve_input_path("missing.mp4", tmp_path, (".mp4",))


def test_resolve_input_path_rejects_extension(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("hello")
    with pytest.raises(ValidationError):
        resolve_input_path("notes.txt", tmp_path, (".mp4",))


def test_resolve_input_path_accepts_relative_file(tmp_path: Path) -> None:
    (tmp_path / "lectures").mkdir()
    video = tmp_path / "lectures" / "one.mp4"
    video.write_bytes(b"video")

    resolved = resolve_input_path("lectures/one.mp4", tmp_path, (".mp4",))

    assert resolved.relative_path == "lectures/one.mp4"
    assert resolved.absolute_path == video.resolve()
    assert resolved.size_bytes == len(b"video")


def test_build_effective_spec_merges_overrides() -> None:
    spec = build_effective_spec(
        {"language": "auto", "model": "small", "output_formats": ["vtt"]},
        {"language": "de"},
    )

    assert spec["language"] == "de"
    assert spec["model"] == "small"
    assert spec["output_formats"] == ["vtt"]
    assert spec["txt_timestamps"] is False
    assert spec["kind"] == "transcribe"


def test_build_effective_spec_preserves_txt_timestamps() -> None:
    spec = build_effective_spec({"txt_timestamps": True})

    assert spec["txt_timestamps"] is True


def test_build_effective_spec_clears_txt_timestamps_without_txt() -> None:
    spec = build_effective_spec(
        {"output_formats": ["vtt"], "txt_timestamps": True}
    )

    assert spec["txt_timestamps"] is False


def test_build_effective_spec_rejects_non_boolean_txt_timestamps() -> None:
    with pytest.raises(ValidationError):
        build_effective_spec({"txt_timestamps": "yes"})


def test_project_defaults_clear_txt_timestamps_without_txt() -> None:
    defaults = ProjectDefaults(output_formats=["vtt"], txt_timestamps=True)

    assert defaults.txt_timestamps is False


def test_build_effective_spec_rejects_unknown_language() -> None:
    with pytest.raises(ValidationError):
        build_effective_spec({"language": "fr"})


def test_spec_hash_is_stable() -> None:
    spec = build_effective_spec({"language": "en"})
    assert spec_hash(spec) == spec_hash(spec)


def test_source_matches_within_tolerance() -> None:
    mtime = datetime.now(UTC)
    assert source_matches(10, mtime, 10, mtime + timedelta(milliseconds=500))
    assert not source_matches(10, mtime, 11, mtime)
    assert not source_matches(10, mtime, 10, mtime + timedelta(seconds=2))


def test_build_frame_spec_snapshots_timecodes() -> None:
    from transcributed.services.spec import build_frame_spec
    from transcributed.services.timecodes import Timecode

    spec = build_frame_spec(
        [Timecode(seconds=83, text="00:01:23"), Timecode(seconds=90, text="00:01:30")]
    )

    assert spec["kind"] == "frames"
    assert spec["image_format"] == "png"
    assert spec["timecodes"] == [
        {"seconds": 83, "timecode": "00:01:23"},
        {"seconds": 90, "timecode": "00:01:30"},
    ]


def test_build_run_spec_uses_frame_workflow() -> None:
    from transcributed.enums import Workflow
    from transcributed.services.spec import build_run_spec

    spec = build_run_spec(Workflow.FRAMES, {"language": "de"})

    assert spec["kind"] == "frames"
    assert "language" not in spec
