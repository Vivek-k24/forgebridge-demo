from types import SimpleNamespace

from partgraph.identity.vehicle.reconciliation import FieldObservation, reconcile_field_observations
from partgraph.identity.vehicle.specification_taxonomy import core_verification_decision


def observation(
    field: str,
    value: object,
    source: str,
    *,
    source_class: str = "vehicle_reference",
    kind: str = "ordinary",
) -> FieldObservation:
    return FieldObservation(
        field=field,
        value=value,
        kind="manufacturer_reported" if kind == "manufacturer_reported" else "ordinary",
        source_name=source,
        source_class=source_class,
    )


def test_three_independent_sources_verify_one_field() -> None:
    result = reconcile_field_observations(
        [
            observation("powertrain.engine.displacement_l", 1.6, "source-a"),
            observation("powertrain.engine.displacement_l", 1.6, "source-b"),
            observation("powertrain.engine.displacement_l", 1.6, "source-c"),
        ]
    )

    field = result["fields"][0]
    assert field["status"] == "verified"
    assert field["match_count"] == 3
    assert field["selected_value"] == 1.6


def test_repeated_records_from_one_source_cannot_satisfy_threshold() -> None:
    result = reconcile_field_observations(
        [
            observation("transmission.family", "CVT", "same-source"),
            observation("transmission.family", "CVT", "same-source"),
            observation("transmission.family", "CVT", "same-source"),
        ]
    )

    field = result["fields"][0]
    assert field["status"] == "candidate"
    assert field["match_count"] == 1


def test_disagreement_is_preserved_instead_of_flattened() -> None:
    result = reconcile_field_observations(
        [
            observation("performance.horsepower_hp", 115, "source-a"),
            observation("performance.horsepower_hp", 115, "source-b"),
            observation("performance.horsepower_hp", 127, "source-c"),
        ]
    )

    field = result["fields"][0]
    assert field["status"] == "conflict"
    assert field["selected_value"] is None
    assert field["match_count"] == 2
    assert field["conflicts"] == [
        {"value": 127, "match_count": 1, "sources": ["source-c"]}
    ]


def test_service_and_fluid_facts_cannot_be_auto_verified_by_generic_sites() -> None:
    result = reconcile_field_observations(
        [
            observation("fluids.engine_oil.capacity_qt", 4.4, "source-a"),
            observation("fluids.engine_oil.capacity_qt", 4.4, "source-b"),
            observation("fluids.engine_oil.capacity_qt", 4.4, "source-c"),
        ]
    )

    field = result["fields"][0]
    assert field["status"] == "candidate"
    assert field["authority"] == "manufacturer_required"


def test_manufacturer_source_can_retain_authoritative_service_fact_without_fake_three_source_label() -> None:
    result = reconcile_field_observations(
        [
            observation(
                "fluids.engine_oil.capacity_qt",
                4.4,
                "honda-service",
                source_class="oem_service",
                kind="manufacturer_reported",
            )
        ]
    )

    field = result["fields"][0]
    assert field["status"] == "manufacturer_reported"
    assert field["selected_value"] == 4.4
    assert field["match_count"] == 1


def test_seed_configuration_requires_every_fact_asserted_by_seed_row() -> None:
    configuration = SimpleNamespace(
        year=1998,
        make="Honda",
        model="CIVIC",
        trim="HX",
        body_style=None,
        drivetrain=None,
        engine="1.6L VTEC-E 4-Cyl (115 hp)",
        transmission="CVT Automatic",
    )
    observations = []
    seed_values = {
        "identity.year": 1998,
        "identity.make": "Honda",
        "identity.model": "CIVIC",
        "identity.trim": "HX",
        "powertrain.engine.displacement_l": 1.6,
        "powertrain.engine.cylinders": 4,
        "powertrain.engine.technology": ["VTEC-E"],
        "performance.horsepower_hp": 115,
        "transmission.family": "CVT",
    }
    for field, value in seed_values.items():
        for source in ("source-a", "source-b", "source-c"):
            observations.append(observation(field, value, source))

    reconciled = reconcile_field_observations(observations)
    core = core_verification_decision(configuration, reconciled["fields"])
    assert core["verified"] is True

    without_horsepower = [
        item for item in observations if item.field != "performance.horsepower_hp"
    ]
    reconciled = reconcile_field_observations(without_horsepower)
    core = core_verification_decision(configuration, reconciled["fields"])
    assert core["verified"] is False
