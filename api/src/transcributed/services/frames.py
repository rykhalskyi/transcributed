from __future__ import annotations

import io
import zipfile
from collections.abc import Sequence

from transcributed.errors import ValidationError
from transcributed.models import TaskFrame

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def frame_filename(index: int, timecode: str) -> str:
    return f"frame-{index:04d}_{timecode.replace(':', '-')}.png"


def parse_png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != PNG_SIGNATURE or data[12:16] != b"IHDR":
        raise ValidationError("ffmpeg did not return a valid PNG image")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    return width, height


def build_frames_zip(frames: Sequence[TaskFrame], manifest: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("manifest.json", manifest)
        for frame in frames:
            archive.writestr(frame.filename, frame.data)
    return buffer.getvalue()
