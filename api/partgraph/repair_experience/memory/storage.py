from __future__ import annotations

import json
import os
import re
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

import anyio
from fastapi import status
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

from ..config import settings
from ..errors import ErrorCode, PartGraphError

_STORAGE_KEY_PATTERN = re.compile(r"^[0-9a-f]{32}\.(?:jpg|png|webp|heic)$")
_BLOB_API_URL = "https://vercel.com/api/blob"
_BLOB_API_VERSION = "12"
_BLOB_TIMEOUT_SECONDS = 5
MAX_PHOTO_PIXELS = 24_000_000
MAX_PHOTO_DIMENSION = 8_192

register_heif_opener()


class PhotoFormatError(ValueError):
    pass


class PhotoResourceLimitError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PreparedPhoto:
    data: bytes
    media_type: str
    extension: str
    width: int
    height: int


def _decoded_format(image: Image.Image) -> str:
    image_format = (image.format or "").upper()
    if image_format not in {"JPEG", "PNG", "WEBP", "HEIF", "HEIC"}:
        raise PhotoFormatError("unsupported image format")
    return image_format


def _assert_image_limits(image: Image.Image) -> None:
    width, height = image.size
    if width < 1 or height < 1:
        raise PhotoFormatError("image dimensions are invalid")
    if width > MAX_PHOTO_DIMENSION or height > MAX_PHOTO_DIMENSION:
        raise PhotoResourceLimitError("image dimensions exceed the allowed limit")
    if width * height > MAX_PHOTO_PIXELS:
        raise PhotoResourceLimitError("decoded image pixel count exceeds the allowed limit")
    if getattr(image, "n_frames", 1) != 1:
        raise PhotoFormatError("animated or multi-frame images are not supported")


def _pixel_copy(image: Image.Image, *, preserve_alpha: bool) -> Image.Image:
    bands = image.getbands()
    has_alpha = "A" in bands or "transparency" in image.info
    target_mode = "RGBA" if preserve_alpha and has_alpha else "RGB"
    return image.convert(target_mode)


def _encode_sanitized(image: Image.Image, source_format: str) -> tuple[bytes, str, str]:
    oriented = ImageOps.exif_transpose(image)
    output = BytesIO()

    if source_format in {"JPEG", "HEIF", "HEIC"}:
        sanitized = _pixel_copy(oriented, preserve_alpha=False)
        sanitized.save(output, format="JPEG", quality=90, optimize=True)
        return output.getvalue(), "image/jpeg", "jpg"

    if source_format == "PNG":
        sanitized = _pixel_copy(oriented, preserve_alpha=True)
        sanitized.save(output, format="PNG", optimize=True, compress_level=9)
        return output.getvalue(), "image/png", "png"

    if source_format == "WEBP":
        sanitized = _pixel_copy(oriented, preserve_alpha=True)
        sanitized.save(output, format="WEBP", quality=90, method=4)
        return output.getvalue(), "image/webp", "webp"

    raise PhotoFormatError("unsupported image format")


def _prepare_photo_sync(data: bytes, maximum_bytes: int) -> PreparedPhoto:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                source_format = _decoded_format(image)
                _assert_image_limits(image)
                image.load()
                width, height = image.size
                encoded, media_type, extension = _encode_sanitized(image, source_format)
    except PhotoResourceLimitError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise PhotoResourceLimitError("image decompression limit exceeded") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise PhotoFormatError("unsupported or malformed image content") from exc

    if not encoded or len(encoded) > maximum_bytes:
        raise PhotoResourceLimitError("sanitized image exceeds the allowed byte limit")

    return PreparedPhoto(
        data=encoded,
        media_type=media_type,
        extension=extension,
        width=width,
        height=height,
    )


async def prepare_photo(data: bytes, *, maximum_bytes: int) -> PreparedPhoto:
    return await anyio.to_thread.run_sync(_prepare_photo_sync, data, maximum_bytes)


def detect_photo_media_type(data: bytes) -> tuple[str, str]:
    """Compatibility helper for already-decoded/sanitized image bytes."""

    prepared = _prepare_photo_sync(data, max(len(data) * 2, settings.photo_max_bytes))
    return prepared.media_type, prepared.extension


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
    static_token = os.getenv("BLOB_READ_WRITE_TOKEN")
    if static_token and static_token.strip():
        return static_token.strip()

    oidc_token = os.getenv("VERCEL_OIDC_TOKEN")
    store_id = os.getenv("BLOB_STORE_ID")
    if oidc_token and oidc_token.strip() and store_id and store_id.strip():
        return oidc_token.strip()
    return None


def _blob_store_id(token: str) -> str:
    configured_store_id = os.getenv("BLOB_STORE_ID")
    if configured_store_id and configured_store_id.strip():
        normalized = configured_store_id.strip()
        if normalized.startswith("store_"):
            normalized = normalized[len("store_") :]
        if normalized:
            return normalized

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


def _media_type_for_storage_key(storage_key: str) -> str:
    extension = storage_key.rsplit(".", 1)[-1]
    media_types = {
        "jpg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "heic": "image/heic",
    }
    try:
        return media_types[extension]
    except KeyError as exc:
        raise PartGraphError(
            code=ErrorCode.PHOTO_STORAGE_CORRUPT,
            message="Photo storage reference has an unsupported media type.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc


def _blob_put(storage_key: str, data: bytes, token: str) -> None:
    store_id = _blob_store_id(token)
    media_type = _media_type_for_storage_key(storage_key)
    url = f"{_BLOB_API_URL}/?{urlencode({'pathname': storage_key})}"
    headers = {
        **_blob_headers(token, store_id=store_id),
        "Content-Type": "application/octet-stream",
        "x-vercel-blob-access": "private",
        "x-add-random-suffix": "0",
        # The deterministic photo ID is the idempotency key. Reconciliation must be
        # able to replay after a database commit acknowledgement is lost.
        "x-allow-overwrite": "1",
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
    except HTTPError as exc:
        if exc.code == 404:
            return
        raise _blob_unavailable() from exc
    except (URLError, TimeoutError) as exc:
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
