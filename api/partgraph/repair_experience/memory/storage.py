from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

import anyio
from fastapi import status

from ..config import settings
from ..errors import ErrorCode, PartGraphError

_STORAGE_KEY_PATTERN = re.compile(r"^[0-9a-f]{32}\.(?:jpg|png|webp|heic)$")
_BLOB_API_URL = "https://vercel.com/api/blob"
_BLOB_API_VERSION = "12"
_BLOB_TIMEOUT_SECONDS = 10


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


def _blob_token() -> str | None:
    value = os.getenv("BLOB_READ_WRITE_TOKEN")
    return value.strip() if value and value.strip() else None


def _blob_store_id(token: str) -> str:
    parts = token.split("_")
    if len(parts) < 5 or not parts[3]:
        raise PartGraphError(
            code=ErrorCode.PHOTO_STORAGE_CORRUPT,
            message="Hosted photo storage credentials are invalid.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return parts[3]


def _blob_headers(token: str, *, store_id: str, attempt: int = 0) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "x-api-blob-request-id": f"{store_id}:{uuid4().hex}",
        "x-vercel-blob-store-id": store_id,
        "x-api-blob-request-attempt": str(attempt),
        "x-api-version": _BLOB_API_VERSION,
    }


def _blob_unavailable() -> PartGraphError:
    return PartGraphError(
        code=ErrorCode.PHOTO_CONTENT_UNAVAILABLE,
        message="Photo content storage is unavailable.",
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        retryable=True,
    )


def _blob_put(storage_key: str, data: bytes, token: str) -> None:
    store_id = _blob_store_id(token)
    media_type, _ = detect_photo_media_type(data)
    url = f"{_BLOB_API_URL}/?{urlencode({'pathname': storage_key})}"
    headers = {
        **_blob_headers(token, store_id=store_id),
        "Content-Type": "application/octet-stream",
        "x-vercel-blob-access": "private",
        "x-add-random-suffix": "0",
        "x-allow-overwrite": "0",
        "x-content-type": media_type,
    }
    try:
        with urlopen(
            Request(url, data=data, headers=headers, method="PUT"),
            timeout=_BLOB_TIMEOUT_SECONDS,
        ) as response:
            payload = json.loads(response.read())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise _blob_unavailable() from exc
    if payload.get("pathname") != storage_key:
        raise PartGraphError(
            code=ErrorCode.PHOTO_STORAGE_CORRUPT,
            message="Hosted photo storage returned an invalid storage reference.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def _blob_get(storage_key: str, token: str) -> bytes:
    store_id = _blob_store_id(token)
    url = f"https://{store_id}.private.blob.vercel-storage.com/{quote(storage_key)}"
    try:
        with urlopen(
            Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET"),
            timeout=_BLOB_TIMEOUT_SECONDS,
        ) as response:
            return response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise _blob_unavailable() from exc


def _blob_delete(storage_key: str, token: str) -> None:
    store_id = _blob_store_id(token)
    data = json.dumps({"urls": [storage_key]}, separators=(",", ":")).encode()
    headers = {
        **_blob_headers(token, store_id=store_id),
        "Content-Type": "application/json",
    }
    try:
        with urlopen(
            Request(f"{_BLOB_API_URL}/delete", data=data, headers=headers, method="POST"),
            timeout=_BLOB_TIMEOUT_SECONDS,
        ) as response:
            response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise _blob_unavailable() from exc


async def store_photo(storage_key: str, data: bytes) -> Path:
    path = _safe_path(storage_key)
    await anyio.to_thread.run_sync(_write_atomic, path, data)
    token = _blob_token()
    if token is None:
        return path
    try:
        await anyio.to_thread.run_sync(_blob_put, storage_key, data, token)
    except Exception:
        await anyio.to_thread.run_sync(path.unlink, True)
        raise
    return path


async def delete_photo_file(storage_key: str) -> None:
    path = _safe_path(storage_key)
    token = _blob_token()
    if token is not None:
        await anyio.to_thread.run_sync(_blob_delete, storage_key, token)
    await anyio.to_thread.run_sync(path.unlink, True)


def photo_path(storage_key: str) -> Path:
    path = _safe_path(storage_key)
    if path.is_file():
        return path
    token = _blob_token()
    if token is not None:
        data = _blob_get(storage_key, token)
        _write_atomic(path, data)
        return path
    raise PartGraphError(
        code=ErrorCode.PHOTO_CONTENT_UNAVAILABLE,
        message="Photo content is unavailable.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        retryable=True,
    )
