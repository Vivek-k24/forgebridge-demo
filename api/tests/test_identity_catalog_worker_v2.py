from __future__ import annotations

import json

import pytest

from partgraph.knowledge import identity_catalog_worker as legacy
from partgraph.knowledge.identity_catalog_worker_v2 import (
    NHTSA_AUTOMOBILE_VEHICLE_TYPES,
    _nhtsa_models,
    _strict_trim_value,
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


def test_nhtsa_network_gap_fails_make_year_instead_of_returning_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        make="Honda",
        year=2025,
    )

    assert set(result) == {"Accord", "Civic"}
    assert result["Civic"]["nhtsa_vpic"] == ["Civic", "Civic Si", "Civic Type R"]
    assert model_variant("Civic", "Civic Si") == "Si"
    assert model_variant("Civic", "Civic 5Dr - Type R") == "Type R"
    assert model_variant("Accord", "Accord Hybrid") == "Hybrid"


def test_configuration_heavy_fueleconomy_labels_fold_into_model_families() -> None:
    result = canonicalize_model_inventory(
        ["TLX", "RDX", "MDX"],
        ["TLX AWD A-SPEC", "TLX FWD A-SPEC", "RDX AWD A-SPEC", "MDX AWD A-SPEC"],
        make="Acura",
        year=2025,
    )

    assert set(result) == {"MDX", "RDX", "TLX"}
    assert result["TLX"]["fueleconomy_gov"] == ["TLX AWD A-SPEC", "TLX FWD A-SPEC"]
    assert model_variant("TLX", "TLX AWD A-SPEC") == "A-Spec"


def test_lexus_engine_designations_do_not_become_separate_models() -> None:
    result = canonicalize_model_inventory(
        ["ES", "GS", "LS", "LX", "SC"],
        ["ES 300", "GS 300", "LS 400", "LX 450", "SC 300/SC 400"],
        make="Lexus",
        year=1996,
    )

    assert set(result) == {"ES", "GS", "LS", "LX", "SC"}
    assert result["ES"]["fueleconomy_gov"] == ["ES 300"]
    assert result["SC"]["fueleconomy_gov"] == ["SC 300/SC 400"]


def test_acura_engine_prefixes_fold_into_rl_and_tl() -> None:
    result = canonicalize_model_inventory(
        ["RL", "TL"],
        ["3.5RL", "2.5TL/3.2TL"],
        make="Acura",
        year=1996,
    )

    assert set(result) == {"RL", "TL"}
    assert result["RL"]["fueleconomy_gov"] == ["3.5RL"]
    assert result["TL"]["fueleconomy_gov"] == ["2.5TL/3.2TL"]


def test_toyota_matrix_alias_and_scion_cross_brand_rows_are_not_canonical_toyota_models() -> None:
    result = canonicalize_model_inventory(
        ["Corolla", "Corolla Matrix", "Scion xB", "Scion tC"],
        ["Corolla", "Matrix", "Matrix AWD"],
        make="Toyota",
        year=2009,
    )

    assert set(result) == {"Corolla", "Matrix"}
    assert result["Matrix"]["nhtsa_vpic"] == ["Corolla Matrix"]
    assert result["Matrix"]["fueleconomy_gov"] == ["Matrix", "Matrix AWD"]


def test_subaru_b9_tribeca_renames_to_tribeca_after_2007() -> None:
    result = canonicalize_model_inventory(
        ["B9 Tribeca", "Forester"],
        ["Tribeca AWD", "Forester AWD"],
        make="Subaru",
        year=2009,
    )

    assert set(result) == {"Forester", "Tribeca"}
    assert result["Tribeca"]["nhtsa_vpic"] == ["B9 Tribeca"]
    assert result["Tribeca"]["fueleconomy_gov"] == ["Tribeca AWD"]


def test_genuine_prime_model_is_not_collapsed() -> None:
    result = canonicalize_model_inventory(
        ["Prius", "Prius Prime (PHEV)"],
        ["Prius", "Prius Prime"],
        make="Toyota",
        year=2025,
    )

    assert set(result) == {"Prius", "Prius Prime"}
    assert result["Prius Prime"]["fueleconomy_gov"] == ["Prius Prime"]
    assert model_variant("Prius", "Prius Prime") is None


def test_trim_filter_rejects_page_chrome_and_spec_cards() -> None:
    assert _strict_trim_value("Based on 541 Consumer Reviews") is None
    assert _strict_trim_value("Learn More About 2025 Honda Civic Type R Cost to Own") is None
    assert _strict_trim_value("Hybrid Select a Trim Base") is None
    assert _strict_trim_value("Sport Utility") is None
    assert _strict_trim_value("Sedan") is None
    assert (
        _strict_trim_value(
            "Touring $37,400 44 MPG 204 @ 5000 RPM 4-Cyl, Hybrid, i-VTEC, 2.0 Liter"
        )
        is None
    )


def test_trim_filter_removes_body_style_tail_without_destroying_trim() -> None:
    assert _strict_trim_value("RT Pickup 4D 5 ft") == "RT"
    assert _strict_trim_value("NSX-T Targa") == "NSX-T"
    assert _strict_trim_value("Sport") == "Sport"
