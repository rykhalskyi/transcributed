from typing import Literal

from fastapi import APIRouter, Query

from transcributed.config import get_settings
from transcributed.schemas import NasDirectory, NasFile, NasListing
from transcributed.services import nas as nas_service

router = APIRouter(prefix="/nas", tags=["nas"])

settings = get_settings()


@router.get("/files", response_model=NasListing)
async def list_nas_files(
    path: str = Query(default="", max_length=1024),
    limit: int = Query(default=500, ge=1, le=2000),
    kind: Literal["video", "timecode"] = Query(default="video"),
) -> NasListing:
    allowed_extensions = (
        settings.timecode_extensions
        if kind == "timecode"
        else settings.allowed_extensions
    )
    listing = nas_service.list_directory(
        settings.nas_input_root,
        path,
        allowed_extensions,
        limit,
    )
    return NasListing(
        path=listing.path,
        parent=listing.parent,
        directories=[
            NasDirectory(name=directory.name, path=directory.path)
            for directory in listing.directories
        ],
        files=[
            NasFile(
                name=file.name,
                path=file.path,
                size_bytes=file.size_bytes,
                mtime=file.mtime,
            )
            for file in listing.files
        ],
        truncated=listing.truncated,
    )
