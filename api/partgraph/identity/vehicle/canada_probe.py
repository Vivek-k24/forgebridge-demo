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


def _model_values(payload: object) -> list[str]:
    if not isinstance(payload, dict) or not isinstance(payload.get("Results"), list):
        return []
    values: list[str] = []
    for row in payload["Results"]:
        if not isinstance(row, dict) or not isinstance(row.get("Specs"), list):
            continue
        for spec in row["Specs"]:
            if (
                isinstance(spec, dict)
                and spec.get("Name") == "Model"
                and isinstance(spec.get("Value"), str)
            ):
                values.append(spec["Value"])
                break
    return values


async def raw_canadian_models(*, year: int, make: str) -> list[str]:
    payload = await asyncio.to_thread(_fetch_sync, year=year, make=make)
    return _model_values(payload)


if __name__ == "__main__":
    samples = (
        (2009, "Acura"),
        (2008, "Volkswagen"),
        (2009, "Honda"),
        (2009, "Pontiac"),
        (2015, "Ford"),
        (2023, "Toyota"),
    )
    print("PARTGRAPH_CANADA_MODEL_PROBE_START")
    for sample_year, sample_make in samples:
        payload = _fetch_sync(year=sample_year, make=sample_make)
        print(f"{sample_year} {sample_make}: {json.dumps(_model_values(payload))}")
    print("PARTGRAPH_CANADA_MODEL_PROBE_END")
