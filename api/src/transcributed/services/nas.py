from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from transcributed.errors import NotFoundError, ValidationError


@dataclass(frozen=True)
class NasDirectoryEntry:
    name: str
    path: str


@dataclass(frozen=True)
class NasFileEntry:
    name: str
    path: str
    size_bytes: int
    mtime: datetime


@dataclass(frozen=True)
class NasListing:
    path: str
    parent: str | None
    directories: list[NasDirectoryEntry]
    files: list[NasFileEntry]
    truncated: bool


def _parse_relative_path(raw: str) -> PurePosixPath:
    value = raw.strip()
    if not value:
        return PurePosixPath()
    if "\x00" in value:
        raise ValidationError("Input path contains a null byte")
    if "\\" in value:
        raise ValidationError("Input path must use forward slashes")
    if "//" in value or value in {".", ".."}:
        raise ValidationError("Input path must not contain empty segments")

    pure = PurePosixPath(value)
    if pure.is_absolute():
        raise ValidationError("Input path must be relative to the NAS input root")
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise ValidationError("Input path must not contain '.', '..', or empty segments")
    return pure


def _as_path(pure: PurePosixPath) -> str:
    return pure.as_posix() if pure.parts else ""


def _join(base: PurePosixPath, name: str) -> str:
    return _as_path(base / name)


def _parent(pure: PurePosixPath) -> str | None:
    if not pure.parts:
        return None
    return _as_path(PurePosixPath(*pure.parts[:-1]))


def list_directory(
    root: Path,
    relative_path: str,
    allowed_extensions: tuple[str, ...],
    limit: int,
) -> NasListing:
    pure = _parse_relative_path(relative_path)
    root_resolved = root.resolve()
    target = (root_resolved / pure).resolve()

    if not target.is_relative_to(root_resolved):
        raise ValidationError("Input path escapes the NAS input root")
    if not target.exists():
        raise NotFoundError("Directory not found")
    if not target.is_dir():
        raise ValidationError("Input path is not a directory")

    allowed = {extension.lower() for extension in allowed_extensions}
    directories: list[NasDirectoryEntry] = []
    files: list[NasFileEntry] = []
    truncated = False

    try:
        entries = sorted(target.iterdir(), key=lambda entry: entry.name.casefold())
    except OSError as exc:
        raise ValidationError("Directory cannot be read") from exc

    for entry in entries:
        try:
            resolved = entry.resolve()
        except OSError:
            continue
        if not resolved.is_relative_to(root_resolved):
            continue

        if entry.is_dir():
            directories.append(
                NasDirectoryEntry(name=entry.name, path=_join(pure, entry.name))
            )
            continue

        if not entry.is_file() or entry.suffix.lower() not in allowed:
            continue
        if len(files) >= limit:
            truncated = True
            continue

        stat = entry.stat()
        files.append(
            NasFileEntry(
                name=entry.name,
                path=_join(pure, entry.name),
                size_bytes=stat.st_size,
                mtime=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            )
        )

    return NasListing(
        path=_as_path(pure),
        parent=_parent(pure),
        directories=directories,
        files=files,
        truncated=truncated,
    )
