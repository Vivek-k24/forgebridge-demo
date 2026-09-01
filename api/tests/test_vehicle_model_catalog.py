import asyncio

import pytest
from fastapi import status
from fastapi.testclient import TestClient

import partgraph.identity.vehicle.model_catalog as model_catalog
import partgraph.identity.vehicle.service as vehicle_service
from partgraph.errors import ErrorCode, PartGraphError
from partgraph.main import app


def test_nhtsa_model_catalog_filters_make_type_normalizes_and_deduplicates() -> None:
    payload = {
        "Results": [
            {
                "Make_Name": "HONDA",
                "Model_Name": "Accord",
                "VehicleTypeName": "Passenger Car",
            },
            {
                "Make_Name": "Honda",
                "Model_Name": " civic ",
                "VehicleTypeName": "Passenger Car",
            },
            {
                "Make_Name": "HONDA",
                "Model_Name": "ACCORD",
                "VehicleTypeName": "Passenger Car",
            },
            {
                "Make_Name": "HONDA",
                "Model_Name": "CR-V",
                "VehicleTypeName": "Multipurpose Passenger Vehicle (MPV)",
            },
            {
                "Make_Name": "HONDA",
                "Model_Name": "Ridgeline",
                "VehicleTypeName": "Truck",
            },
            {
                "Make_Name": "HONDA",
                "Model_Name": "CBR600RR",
                "VehicleTypeName": "Motorcycle",
            },
            {
                "Make_Name": "Honda Power Equipment",
                "Model_Name": "Generator",
                "VehicleTypeName": "Truck",
            },
            {
                "Make_Name": "TOYOTA",
                "Model_Name": "Camry",
                "VehicleTypeName": "Passenger Car",
            },
            {
                "Make_Name": "HONDA",
                "Model_Name": "",
                "VehicleTypeName": "Passenger Car",
            },
            {"Make_Name": None, "Model_Name": "Pilot", "VehicleTypeName": "MPV"},
        ]
    }

    models = model_catalog.parse_nhtsa_model_catalog(payload, expected_make="honda")

    assert models == ("ACCORD", "CIVIC", "CR-V", "RIDGELINE")


def test_nhtsa_model_catalog_rejects_malformed_response() -> None:
    with pytest.raises(PartGraphError) as exc_info:
        model_catalog.parse_nhtsa_model_catalog([], expected_make="Honda")

    assert exc_info.value.code == ErrorCode.VEHICLE_MODEL_PROVIDER_INVALID_RESPONSE
    assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY
    assert exc_info.value.retryable is True


def test_model_catalog_caches_successful_year_make_lookup(monkeypatch) -> None:
    calls: list[tuple[int, str, str]] = []

    def fake_fetch(*, year: int, make: str, vehicle_type: str) -> object:
        calls.append((year, make, vehicle_type))
        if vehicle_type == "truck":
            return {
                "Results": [
                    {
                        "Make_Name": "Honda",
                        "Model_Name": "Ridgeline",
                        "VehicleTypeName": "Truck",
                    }
                ]
            }
        return {
            "Results": [
                {
                    "Make_Name": "Honda",
                    "Model_Name": "Accord",
                    "VehicleTypeName": "Passenger Car",
                },
                {
                    "Make_Name": "Honda",
                    "Model_Name": "Civic",
                    "VehicleTypeName": "Passenger Car",
                },
            ]
        }

    monkeypatch.setattr(model_catalog, "_fetch_sync", fake_fetch)

    async def exercise() -> tuple[tuple[str, ...], tuple[str, ...]]:
        await model_catalog.clear_model_catalog_cache()
        first = await model_catalog.models_for_make_year(year=2009, make="Honda")
        second = await model_catalog.models_for_make_year(year=2009, make="honda")
        return first, second

    first, second = asyncio.run(exercise())

    assert first == ("ACCORD", "CIVIC", "RIDGELINE")
    assert second == first
    assert len(calls) == 2
    assert set(calls) == {
        (2009, "Honda", "passenger"),
        (2009, "Honda", "truck"),
    }


def test_model_endpoint_returns_every_provider_model_without_old_twenty_item_cap(
    monkeypatch,
) -> None:
    expected = tuple(f"MODEL {index:02d}" for index in range(61))

    async def fake_models(*, year: int, make: str) -> tuple[str, ...]:
        assert year == 2022
        assert make == "Toyota"
        return expected

    monkeypatch.setattr(vehicle_service, "models_for_make_year", fake_models)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/vehicle-options/models",
            params={"year": 2022, "market": "US", "make": "Toyota"},
        )

    assert response.status_code == 200
    body = response.json()
    assert set(expected) <= set(body)
    assert len(body) >= len(expected)
    assert "MODEL 60" in body


def test_model_endpoint_filters_locally_after_complete_provider_lookup(monkeypatch) -> None:
    calls = 0

    async def fake_models(*, year: int, make: str) -> tuple[str, ...]:
        nonlocal calls
        calls += 1
        assert year == 2018
        assert make == "Ford"
        return ("EDGE", "ESCAPE", "EXPEDITION", "EXPLORER", "F-150", "MUSTANG")

    monkeypatch.setattr(vehicle_service, "models_for_make_year", fake_models)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/vehicle-options/models",
            params={"year": 2018, "market": "US", "make": "Ford", "q": "exp"},
        )

    assert response.status_code == 200
    assert response.json() == ["EXPEDITION", "EXPLORER"]
    assert calls == 1


def test_provider_discovery_model_does_not_become_canonical_vehicle_truth(monkeypatch) -> None:
    discovered_model = "PROVIDER DISCOVERY ONLY"

    async def fake_models(*, year: int, make: str) -> tuple[str, ...]:
        assert year == 2020
        assert make == "Mazda"
        return (discovered_model,)

    monkeypatch.setattr(vehicle_service, "models_for_make_year", fake_models)

    with TestClient(app) as client:
        models = client.get(
            "/api/v1/vehicle-options/models",
            params={"year": 2020, "market": "US", "make": "Mazda"},
        )
        resolution = client.post(
            "/api/v1/vehicle-selection/resolve",
            json={
                "year": 2020,
                "market": "US",
                "make": "Mazda",
                "model": discovered_model,
            },
        )

    assert models.status_code == 200
    assert discovered_model in models.json()
    assert resolution.status_code == 200
    assert resolution.json()["resolution"] == "manual_candidate"
    assert resolution.json()["matches"] == []


def test_model_provider_failure_is_explicit_not_partial_canonical_fallback(monkeypatch) -> None:
    async def unavailable(*, year: int, make: str) -> tuple[str, ...]:
        del year, make
        raise PartGraphError(
            code=ErrorCode.VEHICLE_MODEL_PROVIDER_UNAVAILABLE,
            message="Vehicle model catalog is temporarily unavailable.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            retryable=True,
        )

    monkeypatch.setattr(vehicle_service, "models_for_make_year", unavailable)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/vehicle-options/models",
            params={"year": 2009, "market": "US", "make": "Honda"},
        )

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "VEHICLE_MODEL_PROVIDER_UNAVAILABLE"
    assert error["retryable"] is True
    assert error["request_id"] == response.headers["x-request-id"]
