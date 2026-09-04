from __future__ import annotations

import asyncio
import json
from threading import Lock
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import status

from ...config import settings
from ...errors import ErrorCode, PartGraphError
from .taxonomy import canonical_make, canonical_model, canonical_trim, compact_key

MAX_PROVIDER_BYTES = 256 * 1024
TRIM_CACHE_TTL_SECONDS = 24 * 60 * 60

_TrimCacheKey = tuple[int, str, str]
_TrimCacheValue = tuple[float, tuple[str, ...]]
_trim_cache: dict[_TrimCacheKey, _TrimCacheValue] = {}
_trim_cache_lock = Lock()


def parse_carsxe_trim_catalog(payload: object) -> tuple[str, ...]:
    """Parse CarsXE trim discovery without creating canonical vehicle truth."""
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise PartGraphError(
            code=ErrorCode.VEHICLE_TRIM_PROVIDER_INVALID_RESPONSE,
            message="Vehicle trim provider returned an invalid response.",
            status_code=status.HTTP_502_BAD_GATEWAY,
            retryable=True,
        )

    trims = payload.get("trims")
    if not isinstance(trims, list):
        raise PartGraphError(
            code=ErrorCode.VEHICLE_TRIM_PROVIDER_INVALID_RESPONSE,
            message="Vehicle trim provider returned an invalid response.",
            status_code=status.HTTP_502_BAD_GATEWAY,
            retryable=True,
        )

    values: dict[str, str] = {}
    for raw in trims:
        if not isinstance(raw, str):
            continue
        trim = canonical_trim(raw)
        if trim is None:
            continue
        values.setdefault(compact_key(trim), trim)
    return tuple(sorted(values.values(), key=str.casefold))


def _provider_error(
    *,
    code: ErrorCode,
    message: str,
    status_code: int,
    retryable: bool,
) -> PartGraphError:
    return PartGraphError(
        code=code,
        message=message,
        status_code=status_code,
        retryable=retryable,
    )


def _fetch_sync(*, year: int, make: str, model: str, api_key: str) -> object:
    query = urlencode(
        {
            "key": api_key,
            "dimension": "trims",
            "year": year,
            "make": make,
            "model": model,
        }
    )
    endpoint = f"{settings.carsxe_base_url}/v1/ymm-options?{query}"
    request = Request(
        endpoint,
        headers={"Accept": "application/json", "User-Agent": "PartGraph/0.9"},
    )

    try:
        with urlopen(request, timeout=settings.trim_provider_timeout_seconds) as response:
            if response.status != 200:
                raise _provider_error(
                    code=ErrorCode.VEHICLE_TRIM_PROVIDER_UNAVAILABLE,
                    message="Vehicle trim catalog is temporarily unavailable.",
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    retryable=True,
                )
            body = response.read(MAX_PROVIDER_BYTES + 1)
    except TimeoutError as exc:
        raise _provider_error(
            code=ErrorCode.VEHICLE_TRIM_PROVIDER_TIMEOUT,
            message="Vehicle trim catalog timed out. Try again.",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            retryable=True,
        ) from exc
    except HTTPError as exc:
        upstream_status = exc.code
        exc.close()
        if upstream_status == 401:
            raise _provider_error(
                code=ErrorCode.VEHICLE_TRIM_PROVIDER_UNAVAILABLE,
                message="Vehicle trim catalog credentials are unavailable.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                retryable=False,
            ) from exc
        raise _provider_error(
            code=ErrorCode.VEHICLE_TRIM_PROVIDER_UNAVAILABLE,
            message="Vehicle trim catalog is temporarily unavailable.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            retryable=upstream_status >= 429,
        ) from exc
    except URLError as exc:
        reason = exc.reason
        timed_out = isinstance(reason, TimeoutError)
        raise _provider_error(
            code=(
                ErrorCode.VEHICLE_TRIM_PROVIDER_TIMEOUT
                if timed_out
                else ErrorCode.VEHICLE_TRIM_PROVIDER_UNAVAILABLE
            ),
            message=(
                "Vehicle trim catalog timed out. Try again."
                if timed_out
                else "Vehicle trim catalog is temporarily unavailable."
            ),
            status_code=(
                status.HTTP_504_GATEWAY_TIMEOUT
                if timed_out
                else status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            retryable=True,
        ) from exc

    if len(body) > MAX_PROVIDER_BYTES:
        raise _provider_error(
            code=ErrorCode.VEHICLE_TRIM_PROVIDER_INVALID_RESPONSE,
            message="Vehicle trim provider response exceeded the allowed size.",
            status_code=status.HTTP_502_BAD_GATEWAY,
            retryable=True,
        )

    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise _provider_error(
            code=ErrorCode.VEHICLE_TRIM_PROVIDER_INVALID_RESPONSE,
            message="Vehicle trim provider returned invalid JSON.",
            status_code=status.HTTP_502_BAD_GATEWAY,
            retryable=True,
        ) from exc


async def trims_for_vehicle(*, year: int, make: str, model: str) -> tuple[str, ...]:
    api_key = settings.carsxe_api_key
    if api_key is None:
        raise _provider_error(
            code=ErrorCode.VEHICLE_TRIM_PROVIDER_UNCONFIGURED,
            message="Vehicle trim catalog is not configured.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            retryable=False,
        )

    normalized_make = canonical_make(make)
    normalized_model = canonical_model(model)
    cache_key = (year, normalized_make, normalized_model)
    now = monotonic()

    with _trim_cache_lock:
        cached = _trim_cache.get(cache_key)
        if cached is not None:
            cached_at, trims = cached
            if now - cached_at < TRIM_CACHE_TTL_SECONDS:
                return trims
            _trim_cache.pop(cache_key, None)

    payload = await asyncio.to_thread(
        _fetch_sync,
        year=year,
        make=normalized_make,
        model=normalized_model,
        api_key=api_key,
    )
    trims = parse_carsxe_trim_catalog(payload)

    with _trim_cache_lock:
        _trim_cache[cache_key] = (monotonic(), trims)

    return trims


async def clear_trim_catalog_cache() -> None:
    """Test/support seam; production cache entries expire automatically."""
    with _trim_cache_lock:
        _trim_cache.clear()
