from __future__ import annotations

import asyncio
import json
from threading import Lock
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from fastapi import status

from ...config import settings
from ...errors import ErrorCode, PartGraphError
from .taxonomy import canonical_make, canonical_model, compact_key

MAX_PROVIDER_BYTES = 512 * 1024
MODEL_CACHE_TTL_SECONDS = 24 * 60 * 60

_ModelCacheKey = tuple[int, str]
_ModelCacheValue = tuple[float, tuple[str, ...]]
_model_cache: dict[_ModelCacheKey, _ModelCacheValue] = {}
_model_cache_lock = Lock()


def parse_nhtsa_model_catalog(payload: object, *, expected_make: str) -> tuple[str, ...]:
    """Parse vPIC model discovery without promoting it into canonical vehicle truth."""
    if not isinstance(payload, dict):
        raise PartGraphError(
            code=ErrorCode.VEHICLE_MODEL_PROVIDER_INVALID_RESPONSE,
            message="Vehicle model provider returned an invalid response.",
            status_code=status.HTTP_502_BAD_GATEWAY,
            retryable=True,
        )

    results = payload.get("Results")
    if not isinstance(results, list):
        raise PartGraphError(
            code=ErrorCode.VEHICLE_MODEL_PROVIDER_INVALID_RESPONSE,
            message="Vehicle model provider returned an invalid response.",
            status_code=status.HTTP_502_BAD_GATEWAY,
            retryable=True,
        )

    expected_make_key = compact_key(canonical_make(expected_make))
    models: dict[str, str] = {}
    for row in results:
        if not isinstance(row, dict):
            continue

        make_name = row.get("Make_Name")
        model_name = row.get("Model_Name")
        if not isinstance(make_name, str) or not isinstance(model_name, str):
            continue
        if compact_key(make_name) != expected_make_key:
            # The vPIC endpoint accepts partial make names. PartGraph does not allow
            # a partial match to contaminate a supported make's model selector.
            continue

        try:
            model = canonical_model(model_name)
        except ValueError:
            continue
        models.setdefault(compact_key(model), model)

    return tuple(sorted(models.values(), key=str.casefold))


def _fetch_sync(*, year: int, make: str) -> object:
    endpoint = (
        f"{settings.nhtsa_base_url}/GetModelsForMakeYear/"
        f"make/{quote(make, safe='')}/modelyear/{year}?format=json"
    )
    request = Request(
        endpoint,
        headers={"Accept": "application/json", "User-Agent": "PartGraph/0.9"},
    )

    try:
        with urlopen(request, timeout=settings.nhtsa_timeout_seconds) as response:
            if response.status != 200:
                raise PartGraphError(
                    code=ErrorCode.VEHICLE_MODEL_PROVIDER_UNAVAILABLE,
                    message="Vehicle model catalog is temporarily unavailable.",
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    retryable=True,
                )
            body = response.read(MAX_PROVIDER_BYTES + 1)
    except TimeoutError as exc:
        raise PartGraphError(
            code=ErrorCode.VEHICLE_MODEL_PROVIDER_TIMEOUT,
            message="Vehicle model catalog timed out. Try again.",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            retryable=True,
        ) from exc
    except HTTPError as exc:
        exc.close()
        raise PartGraphError(
            code=ErrorCode.VEHICLE_MODEL_PROVIDER_UNAVAILABLE,
            message="Vehicle model catalog is temporarily unavailable.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            retryable=True,
        ) from exc
    except URLError as exc:
        reason = exc.reason
        timed_out = isinstance(reason, TimeoutError)
        raise PartGraphError(
            code=(
                ErrorCode.VEHICLE_MODEL_PROVIDER_TIMEOUT
                if timed_out
                else ErrorCode.VEHICLE_MODEL_PROVIDER_UNAVAILABLE
            ),
            message=(
                "Vehicle model catalog timed out. Try again."
                if timed_out
                else "Vehicle model catalog is temporarily unavailable."
            ),
            status_code=(
                status.HTTP_504_GATEWAY_TIMEOUT
                if timed_out
                else status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            retryable=True,
        ) from exc

    if len(body) > MAX_PROVIDER_BYTES:
        raise PartGraphError(
            code=ErrorCode.VEHICLE_MODEL_PROVIDER_INVALID_RESPONSE,
            message="Vehicle model provider response exceeded the allowed size.",
            status_code=status.HTTP_502_BAD_GATEWAY,
            retryable=True,
        )

    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PartGraphError(
            code=ErrorCode.VEHICLE_MODEL_PROVIDER_INVALID_RESPONSE,
            message="Vehicle model provider returned invalid JSON.",
            status_code=status.HTTP_502_BAD_GATEWAY,
            retryable=True,
        ) from exc


async def models_for_make_year(*, year: int, make: str) -> tuple[str, ...]:
    normalized_make = canonical_make(make)
    cache_key = (year, normalized_make)
    now = monotonic()

    with _model_cache_lock:
        cached = _model_cache.get(cache_key)
        if cached is not None:
            cached_at, models = cached
            if now - cached_at < MODEL_CACHE_TTL_SECONDS:
                return models
            _model_cache.pop(cache_key, None)

    payload = await asyncio.to_thread(_fetch_sync, year=year, make=normalized_make)
    models = parse_nhtsa_model_catalog(payload, expected_make=normalized_make)

    with _model_cache_lock:
        _model_cache[cache_key] = (monotonic(), models)

    return models


async def clear_model_catalog_cache() -> None:
    """Test/support seam; production cache entries expire automatically."""
    with _model_cache_lock:
        _model_cache.clear()
