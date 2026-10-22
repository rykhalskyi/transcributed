from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from transcributed.errors import ValidationError
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
