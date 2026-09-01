from __future__ import annotations

import asyncio
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ...config import settings


def _fetch_sync(*, year: int, make: str) -> object:
    query = urlencode({"year": year, "make": make, "format": "json"})
    request = Request(
        f"{settings.nhtsa_base_url}/GetCanadianVehicleSpecifications/?{query}",
        headers={"Accept": "application/json", "User-Agent": "PartGraph/0.9"},
    )
    with urlopen(request, timeout=settings.nhtsa_timeout_seconds) as response:
        return json.loads(response.read(512 * 1024))


async def raw_canadian_models(*, year: int, make: str) -> list[str]:
    payload = await asyncio.to_thread(_fetch_sync, year=year, make=make)
    if not isinstance(payload, dict) or not isinstance(payload.get("Results"), list):
        return [json.dumps(payload, sort_keys=True)[:2000]]
    return [
        json.dumps(row, sort_keys=True)
        for row in payload["Results"][:25]
        if isinstance(row, dict)
    ]
