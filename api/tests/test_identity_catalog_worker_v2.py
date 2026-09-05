from __future__ import annotations

import json

import pytest

from partgraph.knowledge import identity_catalog_worker as legacy
from partgraph.knowledge.identity_catalog_worker_v2 import (
    NHTSA_AUTOMOBILE_VEHICLE_TYPES,
    _nhtsa_models,
    canonicalize_model_inventory,
    model_variant,
)


def _payload(*models: str) -> bytes:
    return json.dumps({"Results": [{"Model_Name": model} for model in models]}).encode()


def test_nhtsa_scope_is_only_consumer_road_vehicle_classes(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_urls: list[str] = []

    def fake_fetch_cached(provider, make, year, url, **kwargs):
        seen_urls.append(url)
        if "Passenger%20Car" in url:
            return _payload("Accord", "Civic", "Civic Si", "Civic Type R"), {"status": "success"}
        if "Multipurpose%20Passenger%20Vehicle%20%28MPV%29" in url:
            return _payload("CR-V", "Pilot"), {"status": "success"}
        if "/vehicletype/Truck" in url:
            return _payload("Ridgeline"), {"status": "success"}
        raise AssertionError(url)

    monkeypatch.setattr(legacy, "_fetch_cached", fake_fetch_cached)
    models, evidence = _nhtsa_models("Honda", 2024, False)

    assert models == ["Accord", "Civic", "Civic Si", "Civic Type R", "CR-V", "Pilot", "Ridgeline"]
    assert len(seen_urls) == 3
    assert all("vehicletype" in url for url in seen_urls)
    assert evidence["vehicle_type_scope"] == list(NHTSA_AUTOMOBILE_VEHICLE_TYPES)


def test_nhtsa_network_gap_fails_make_year_instead_of_returning_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_fetch_cached(provider, make, year, url, **kwargs):
        if "/vehicletype/Truck" in url:
            return None, {"status": "failed", "error": "offline"}
        return _payload(), {"status": "success"}

    monkeypatch.setattr(legacy, "_fetch_cached", fake_fetch_cached)

    with pytest.raises(RuntimeError, match="refusing to mark"):
        _nhtsa_models("Hyundai", 2018, False)


def test_civic_si_and_type_r_are_distinct_trims_under_civic() -> None:
    result = canonicalize_model_inventory(
        ["Civic", "Civic Si", "Civic Type R", "Accord", "Accord Hybrid"],
        ["Civic", "Civic Si", "Civic Type R", "Accord Hybrid"],
    )

    assert set(result) == {"Accord", "Civic"}
    assert result["Civic"]["nhtsa_vpic"] == ["Civic", "Civic Si", "Civic Type R"]
    assert model_variant("Civic", "Civic Si") == "Si"
    assert model_variant("Civic", "Civic Type R") == "Type R"
    assert model_variant("Accord", "Accord Hybrid") == "Hybrid"


def test_genuine_prime_model_is_not_collapsed() -> None:
    result = canonicalize_model_inventory(
        ["Prius", "Prius Prime"],
        ["Prius", "Prius Prime"],
    )

    assert set(result) == {"Prius", "Prius Prime"}
    assert model_variant("Prius", "Prius Prime") is None
