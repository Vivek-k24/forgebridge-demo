import json
from uuid import uuid4

from partgraph.identity.vehicle.models import VehicleConfiguration
from partgraph.identity.vehicle.specification_taxonomy import (
    observation_comparison_key,
    split_engine_descriptor,
    split_transmission_descriptor,
)
from partgraph.knowledge.workbench_source_pipeline import extract_source, source_requests


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


def test_engine_descriptor_is_split_into_independent_facts() -> None:
    fields = split_engine_descriptor("1.6L VTEC-E 4-Cyl (115 hp)")

    assert fields["powertrain.engine.displacement_l"] == 1.6
    assert fields["powertrain.engine.cylinders"] == 4
    assert fields["powertrain.engine.technology"] == ["VTEC-E"]
    assert fields["performance.horsepower_hp"] == 115


def test_transmission_descriptor_is_not_part_of_trim_identity() -> None:
    fields = split_transmission_descriptor("CVT Automatic")

    assert fields == {"transmission.family": "CVT"}


def test_trim_punctuation_variants_compare_equal_without_merging_distinct_trims() -> None:
    assert observation_comparison_key(
        "identity.trim", "EX-L"
    ) == observation_comparison_key("identity.trim", "EX L")
    assert observation_comparison_key(
        "identity.trim", "XLE"
    ) != observation_comparison_key("identity.trim", "XLE Premium")


def test_reference_page_emits_partial_fields_without_whole_row_vote() -> None:
    configuration = civic_hx()
    html = b"""
    <html><body>
      <h1>1998 Honda Civic HX</h1>
      <section>HX 1.6L VTEC-E 4-cylinder engine producing 115 hp.</section>
    </body></html>
    """

    extraction = extract_source("kbb", html, "text/html", configuration)

    assert extraction.matched_fields["year"] is True
    assert extraction.matched_fields["make"] is True
    assert extraction.matched_fields["model"] is True
    assert extraction.matched_fields["trim"] is True
    assert extraction.matched_fields["configuration_match"] is False
    assert extraction.field_observations["identity.trim"]["value"] == "HX"
    assert (
        extraction.field_observations["powertrain.engine.displacement_l"]["value"]
        == 1.6
    )
    assert extraction.field_observations["powertrain.engine.cylinders"]["value"] == 4
    assert extraction.field_observations["performance.horsepower_hp"]["value"] == 115
    assert "transmission.family" not in extraction.field_observations


def test_nhtsa_model_result_supports_model_year_identity_only() -> None:
    configuration = civic_hx()
    raw = json.dumps(
        {
            "Results": [
                {"Make_Name": "Honda", "Model_Name": "Civic"},
                {"Make_Name": "Honda", "Model_Name": "Accord"},
            ]
        }
    ).encode()

    extraction = extract_source("nhtsa_vpic", raw, "application/json", configuration)

    assert set(extraction.field_observations) == {
        "identity.year",
        "identity.make",
        "identity.model",
    }
    assert extraction.matched_fields["configuration_match"] is False


def test_source_registry_is_extensible_and_has_no_five_source_ceiling() -> None:
    providers = [request.source_key for request in source_requests(civic_hx())]

    assert providers[:2] == ["nhtsa_vpic", "fueleconomy_gov"]
    assert {"cars_com", "edmunds", "kbb", "motortrend"}.issubset(providers)
    assert len(providers) >= 6
    assert len(providers) == len(set(providers))
