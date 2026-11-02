import io
import zipfile

import pytest

from transcributed.errors import ValidationError
from transcributed.models import TaskFrame
from transcributed.services.frames import (
    build_frames_zip,
    frame_filename,
    parse_png_dimensions,
)
from transcributed.worker.frames import FAKE_PNG


def test_parse_png_dimensions_reads_ihdr() -> None:
    assert parse_png_dimensions(FAKE_PNG) == (1, 1)


def test_parse_png_dimensions_rejects_invalid_data() -> None:
    with pytest.raises(ValidationError):
        parse_png_dimensions(b"not a png")


def test_frame_filename_is_stable() -> None:
    assert frame_filename(3, "01:02:03") == "frame-0003_01-02-03.png"


def test_build_frames_zip_contains_manifest_and_frames() -> None:
    frame = TaskFrame(
        task_id=__import__("uuid").uuid4(),
        index=1,
        timecode_seconds=10.0,
        timecode="00:00:10",
        filename="frame-0001_00-00-10.png",
        content_type="image/png",
        width=1,
        height=1,
        size_bytes=len(FAKE_PNG),
        sha256="0" * 64,
        data=FAKE_PNG,
    )

    payload = build_frames_zip([frame], '{"extracted": 1}')

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert sorted(archive.namelist()) == ["frame-0001_00-00-10.png", "manifest.json"]
        assert archive.read("manifest.json") == b'{"extracted": 1}'
        assert archive.read("frame-0001_00-00-10.png") == FAKE_PNG
