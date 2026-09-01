import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

import partgraph.identity.vehicle.service as vehicle_service
import partgraph.identity.vehicle.trim_catalog as trim_catalog
from partgraph.database import session_factory
from partgraph.errors import ErrorCode, PartGraphError
from partgraph.main import app
from partgraph.vehicle.schemas import VehicleConfigurationInput
from partgraph.vehicle.service import resolve_configuration


def seed_configuration(payload: dict[str, object]) -> None:
    async def seed() -> None:
        async with session_factory() as session:
            await resolve_configuration(
                session,
                VehicleConfigurationInput.model_validate(payload),
            )

    asyncio.run(seed())


def test_carsxe_trim_catalog_normalizes_and_deduplicates() -> None:
    payload = {
        "success": True,
        "input": {
            "dimension": "trims",
            "year": "2009",
            "make": "Honda",
            "model": "Civic",
        },
        "trims": ["LX", " ex ", "EX", "Hybrid", "", None],
    }

    trims = trim_catalog.parse_carsxe_trim_catalog(payload)

    assert trims == ("EX", "HYBRID", "LX")


def test_carsxe_trim_catalog_rejects_malformed_response() -> None:
    with pytest.raises(PartGraphError) as exc_info:
        trim_catalog.parse_carsxe_trim_catalog({"success": True, "variants": ["Civic EX"]})

    assert exc_info.value.code == ErrorCode.VEHICLE_TRIM_PROVIDER_INVALID_RESPONSE
    assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY
    assert exc_info.value.retryable is True


def test_trim_catalog_requires_configured_provider() -> None:
    original_settings = trim_catalog.settings
    trim_catalog.settings = SimpleNamespace(carsxe_api_key=None)
    try:
        with pytest.raises(PartGraphError) as exc_info:
            asyncio.run(
                trim_catalog.trims_for_vehicle(
                    year=2009,
                    make="Honda",
                    model="Civic",
                )
            )
    finally:
        trim_catalog.settings = original_settings

    assert exc_info.value.code == ErrorCode.VEHICLE_TRIM_PROVIDER_UNCONFIGURED
    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert exc_info.value.retryable is False


def test_trim_catalog_caches_successful_vehicle_lookup(monkeypatch) -> None:
    calls: list[tuple[int, str, str, str]] = []

    def fake_fetch(*, year: int, make: str, model: str, api_key: str) -> object:
        calls.append((year, make, model, api_key))
        return {"success": True, "trims": ["LE", "SE", "XLE", "XSE"]}

    monkeypatch.setattr(trim_catalog, "_fetch_sync", fake_fetch)
    monkeypatch.setattr(
        trim_catalog,
        "settings",
        SimpleNamespace(carsxe_api_key="sandbox-test-key"),
    )

    async def exercise() -> tuple[tuple[str, ...], tuple[str, ...]]:
        await trim_catalog.clear_trim_catalog_cache()
        first = await trim_catalog.trims_for_vehicle(
            year=2023,
            make="Toyota",
            model="Camry",
        )
        second = await trim_catalog.trims_for_vehicle(
            year=2023,
            make="toyota",
            model="camry",
        )
        return first, second

    first, second = asyncio.run(exercise())

    assert first == ("LE", "SE", "XLE", "XSE")
    assert second == first
    assert calls == [(2023, "Toyota", "CAMRY", "sandbox-test-key")]


def test_trim_endpoint_returns_every_provider_trim_without_old_twenty_item_cap(
    monkeypatch,
) -> None:
    expected = tuple(f"TRIM {index:02d}" for index in range(61))

    async def fake_trims(*, year: int, make: str, model: str) -> tuple[str, ...]:
        assert year == 2022
        assert make == "Toyota"
        assert model == "TUNDRA"
        return expected

    monkeypatch.setattr(vehicle_service, "trims_for_vehicle", fake_trims)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/vehicle-options/trims",
            params={
                "year": 2022,
                "market": "US",
                "make": "Toyota",
                "model": "Tundra",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert set(expected) <= set(body)
    assert len(body) >= len(expected)
    assert "TRIM 60" in body


def test_trim_endpoint_filters_locally_after_complete_provider_lookup(monkeypatch) -> None:
    calls = 0

    async def fake_trims(*, year: int, make: str, model: str) -> tuple[str, ...]:
        nonlocal calls
        calls += 1
        assert year == 2009
        assert make == "Honda"
        assert model == "CIVIC"
        return ("DX", "DX-G", "EX", "EX-L", "HYBRID", "LX", "LX-S", "SI")

    monkeypatch.setattr(vehicle_service, "trims_for_vehicle", fake_trims)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/vehicle-options/trims",
            params={
                "year": 2009,
                "market": "US",
                "make": "Honda",
                "model": "Civic",
                "q": "lx",
            },
        )

    assert response.status_code == 200
    assert response.json() == ["LX", "LX-S"]
    assert calls == 1


def test_trim_endpoint_unions_reviewed_canonical_trim(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    model = f"Provider-Union-{suffix}"
    seed_configuration(
        {
            "year": 2018,
            "market": "US",
            "make": "Ford",
            "model": model,
            "trim": "Verified Local",
        }
    )

    async def fake_trims(*, year: int, make: str, model: str) -> tuple[str, ...]:
        assert year == 2018
        assert make == "Ford"
        assert model.startswith("PROVIDER-UNION-")
        return ("PROVIDER A", "PROVIDER B")

    monkeypatch.setattr(vehicle_service, "trims_for_vehicle", fake_trims)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/vehicle-options/trims",
            params={
                "year": 2018,
                "market": "US",
                "make": "Ford",
                "model": model,
            },
        )

    assert response.status_code == 200
    assert set(response.json()) == {"PROVIDER A", "PROVIDER B", "VERIFIED LOCAL"}


def test_provider_discovery_trim_does_not_become_canonical_vehicle_truth(monkeypatch) -> None:
    discovered_trim = f"PROVIDER-ONLY-{uuid4().hex[:8]}"

    async def fake_trims(*, year: int, make: str, model: str) -> tuple[str, ...]:
        assert year == 2020
        assert make == "Mazda"
        assert model == "CX-5"
        return (discovered_trim,)

    monkeypatch.setattr(vehicle_service, "trims_for_vehicle", fake_trims)

    with TestClient(app) as client:
        trims = client.get(
            "/api/v1/vehicle-options/trims",
            params={
                "year": 2020,
                "market": "US",
                "make": "Mazda",
                "model": "CX-5",
                "q": discovered_trim,
            },
        )
        resolution = client.post(
            "/api/v1/vehicle-selection/resolve",
            json={
                "year": 2020,
                "market": "US",
                "make": "Mazda",
                "model": "CX-5",
                "trim": discovered_trim,
            },
        )

    assert trims.status_code == 200
    assert discovered_trim.upper() in trims.json()
    assert resolution.status_code == 200
    assert resolution.json()["resolution"] == "manual_candidate"
    assert resolution.json()["matches"] == []


def test_trim_provider_failure_is_explicit_not_partial_canonical_fallback(monkeypatch) -> None:
    async def unavailable(*, year: int, make: str, model: str) -> tuple[str, ...]:
        del year, make, model
        raise PartGraphError(
            code=ErrorCode.VEHICLE_TRIM_PROVIDER_UNAVAILABLE,
            message="Vehicle trim catalog is temporarily unavailable.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            retryable=True,
        )

    monkeypatch.setattr(vehicle_service, "trims_for_vehicle", unavailable)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/vehicle-options/trims",
            params={
                "year": 2009,
                "market": "US",
                "make": "Honda",
                "model": "Civic",
            },
        )

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "VEHICLE_TRIM_PROVIDER_UNAVAILABLE"
    assert error["retryable"] is True
    assert error["request_id"] == response.headers["x-request-id"]
