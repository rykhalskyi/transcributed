from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from transcributed.errors import ValidationError
from transcributed.schemas import ProjectDefaults

SUPPORTED_LANGUAGES = frozenset({"en", "ru", "de", "auto"})
SUPPORTED_MODELS = frozenset({"tiny", "base", "small", "medium", "large-v3"})
SUPPORTED_OUTPUT_FORMATS = frozenset({"vtt", "json", "txt"})
SPEC_VERSION = 1


@dataclass(frozen=True)
class ResolvedInput:
    relative_path: str
    absolute_path: Path
    size_bytes: int
    mtime: datetime


def resolve_input_path(
    relative_path: str,
    root: Path,
    allowed_extensions: tuple[str, ...],
) -> ResolvedInput:
    raw = relative_path.strip()
    if not raw:
        raise ValidationError("Input path is empty")
    if "\x00" in raw:
        raise ValidationError("Input path contains a null byte")
    if "\\" in raw:
        raise ValidationError("Input path must use forward slashes")

    pure = PurePosixPath(raw)
    if pure.is_absolute():
        raise ValidationError("Input path must be relative to the NAS input root")
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise ValidationError("Input path must not contain '.', '..', or empty segments")

    root_resolved = root.resolve()
    candidate = (root_resolved / pure).resolve()

    if not candidate.is_relative_to(root_resolved):
        raise ValidationError("Input path escapes the NAS input root")
    if not candidate.exists():
        raise ValidationError("Input file does not exist")
    if not candidate.is_file():
        raise ValidationError("Input path is not a regular file")

    allowed = {extension.lower() for extension in allowed_extensions}
    if candidate.suffix.lower() not in allowed:
        raise ValidationError(f"Unsupported file extension: {candidate.suffix or '<none>'}")

    stat = candidate.stat()
    return ResolvedInput(
        relative_path=pure.as_posix(),
        absolute_path=candidate,
        size_bytes=stat.st_size,
        mtime=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
    )


def build_effective_spec(
    defaults: dict[str, Any] | None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = ProjectDefaults().model_dump()
    if defaults:
        base.update(defaults)
    if overrides:
        for key in ("language", "model"):
            if overrides.get(key) is not None:
                base[key] = overrides[key]

    language = base.get("language", "auto")
    model = base.get("model", "small")
    output_formats = base.get("output_formats", ["txt"])

    if language not in SUPPORTED_LANGUAGES:
        raise ValidationError(f"Unsupported language: {language}")
    if model not in SUPPORTED_MODELS:
        raise ValidationError(f"Unsupported model: {model}")
    if not output_formats:
        raise ValidationError("At least one output format is required")
    for output_format in output_formats:
        if output_format not in SUPPORTED_OUTPUT_FORMATS:
            raise ValidationError(f"Unsupported output format: {output_format}")

    return {
        "spec_version": SPEC_VERSION,
        "kind": "transcribe",
        "language": language,
        "model": model,
        "output_formats": list(dict.fromkeys(output_formats)),
    }


def spec_hash(spec: dict[str, Any]) -> str:
    canonical = json.dumps(spec, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def source_matches(
    size_bytes: int,
    mtime: datetime,
    current_size_bytes: int,
    current_mtime: datetime,
) -> bool:
    if size_bytes != current_size_bytes:
        return False
    return abs((mtime - current_mtime).total_seconds()) < 1
