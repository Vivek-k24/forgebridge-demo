from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import UUID

import anyio

from ..config import settings
from ..errors import ErrorCode, PartGraphError
from fastapi import status

_STORAGE_KEY_PATTERN = re.compile(r"^[0-9a-f]{32}\.(?:jpg|png|webp|heic)$")


class PhotoFormatError(ValueError):
    pass


def detect_photo_media_type(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12]
        compatible = data[16:64]
        heif_brands = (b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1")
        if brand in heif_brands or any(item in compatible for item in heif_brands):
            return "image/heic", "heic"
    raise PhotoFormatError("unsupported or malformed image content")


def new_storage_key(photo_id: UUID, extension: str) -> str:
    return f"{photo_id.hex}.{extension}"


def _safe_path(storage_key: str) -> Path:
    if _STORAGE_KEY_PATTERN.fullmatch(storage_key) is None:
        raise PartGraphError(
            code=ErrorCode.PHOTO_STORAGE_CORRUPT,
            message="Photo storage reference is invalid.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    root = Path(settings.media_root).resolve()
    path = (root / storage_key).resolve()
    if path.parent != root:
        raise PartGraphError(
            code=ErrorCode.PHOTO_STORAGE_CORRUPT,
            message="Photo storage reference escaped its private storage root.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return path


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


async def store_photo(storage_key: str, data: bytes) -> Path:
    path = _safe_path(storage_key)
    await anyio.to_thread.run_sync(_write_atomic, path, data)
    return path


async def delete_photo_file(storage_key: str) -> None:
    path = _safe_path(storage_key)
    await anyio.to_thread.run_sync(path.unlink, True)


def photo_path(storage_key: str) -> Path:
    path = _safe_path(storage_key)
    if not path.is_file():
        raise PartGraphError(
            code=ErrorCode.PHOTO_CONTENT_UNAVAILABLE,
            message="Photo content is unavailable.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            retryable=True,
        )
    return path
