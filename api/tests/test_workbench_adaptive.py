from uuid import uuid4

from partgraph.identity.vehicle.models import VehicleConfiguration
from partgraph.knowledge.workbench_adaptive import (
    GapAnalysis,
    analyze_gaps,
    field_group,
    matching_fueleconomy_models,
    plan_source_requests,
)


def civic_hx() -> VehicleConfiguration:
    return VehicleConfiguration(
        id=uuid4(),
        identity_hash=uuid4().hex,
        base_identity_hash=uuid4().hex,
        year=1998,
        market="US",
        make="Honda",
        model="CIVIC",
        trim="HX",
        engine="1.6L VTEC-E 4-Cyl (115 hp)",
        transmission="CVT Automatic",
        drivetrain=None,
        identity_source="workbook",
        verification_status="unverified",
    )


def crv() -> VehicleConfiguration:
    return VehicleConfiguration(
        id=uuid4(),
        identity_hash=uuid4().hex,
        base_identity_hash=uuid4().hex,
        year=1998,
        market="US",
        make="Honda",
        model="CR-V",
        trim="LX",
        engine="2.0L 4-Cyl (126 hp)",
        transmission="4-Speed Automatic",
        drivetrain=None,
        identity_source="workbook",
        verification_status="unverified",
    )


def test_horsepower_gap_does_not_query_sources_that_cannot_supply_horsepower() -> None:
    configuration = civic_hx()
    gaps = GapAnalysis(("performance.horsepower_hp",), ())

    broad = plan_source_requests(configuration, gaps, {}, set(), phase="broad")
    gap = plan_source_requests(configuration, gaps, {}, set(), phase="gap")

    assert [plan.request.source_key for plan in broad] == ["kbb", "motortrend"]
    assert [plan.request.source_key for plan in gap] == ["cars_com", "edmunds"]
    assert all(plan.capability_groups == ("performance",) for plan in broad + gap)


def test_provider_that_already_observed_requested_field_is_not_replayed_for_no_reason() -> None:
    configuration = civic_hx()
    gaps = GapAnalysis(("performance.horsepower_hp",), ())

    plans = plan_source_requests(
        configuration,
        gaps,
        {"kbb": {"performance.horsepower_hp"}},
        set(),
        phase="broad",
    )

    assert [plan.request.source_key for plan in plans] == ["motortrend"]


def test_engine_gap_selects_engine_capable_broad_sources_but_not_nhtsa() -> None:
    configuration = civic_hx()
    gaps = GapAnalysis(("powertrain.engine.displacement_l",), ())

    plans = plan_source_requests(configuration, gaps, {}, set(), phase="broad")

    assert [plan.request.source_key for plan in plans] == [
        "fueleconomy_gov",
        "kbb",
        "motortrend",
    ]


def test_gap_analysis_finishes_seed_core_before_enrichment() -> None:
    configuration = civic_hx()
    field_results = [
        {
            "field": "identity.year",
            "status": "verified",
            "selected_value": 1998,
        },
        {
            "field": "identity.make",
            "status": "verified",
            "selected_value": "Honda",
        },
        {
            "field": "identity.model",
            "status": "verified",
            "selected_value": "CIVIC",
        },
        {
            "field": "efficiency.epa_city_mpg",
            "status": "conflict",
            "selected_value": None,
        },
    ]

    gaps = analyze_gaps(configuration, field_results)

    assert "identity.year" not in gaps.core_fields
    assert "identity.make" not in gaps.core_fields
    assert "identity.model" not in gaps.core_fields
    assert "identity.trim" in gaps.core_fields
    assert "performance.horsepower_hp" in gaps.core_fields
    assert gaps.active_fields == gaps.core_fields
    assert gaps.enrichment_fields == ("efficiency.epa_city_mpg",)


def test_fueleconomy_model_discovery_handles_source_expanded_crv_names() -> None:
    configuration = crv()

    matches = matching_fueleconomy_models(
        configuration,
        ["Accord", "CR-V 2WD", "CR-V 4WD", "Civic"],
    )

    assert matches == ["CR-V 2WD", "CR-V 4WD"]


def test_field_groups_support_future_parts_adapters_without_mixing_authority() -> None:
    assert field_group("performance.horsepower_hp") == "performance"
    assert field_group("transmission.family") == "transmission_drivetrain"
    assert field_group("fitment.oem_part_number") == "parts_fitment"
    assert field_group("service.engine_oil.capacity_qt") == "service_fluids"
