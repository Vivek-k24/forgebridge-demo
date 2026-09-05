import json
from uuid import uuid4

from partgraph.identity.vehicle.models import VehicleConfiguration
from partgraph.identity.vehicle.specification_taxonomy import (
    observation_comparison_key,
    split_engine_descriptor,
    split_transmission_descriptor,
)
from partgraph.knowledge.workbench_source_pipeline import extract_source, source_requests


def configuration(
    *,
    year: int = 1998,
    make: str = "Honda",
    model: str = "CIVIC",
    trim: str | None = "HX",
    engine: str | None = "1.6L VTEC-E 4-Cyl (115 hp)",
    transmission: str | None = "CVT Automatic",
) -> VehicleConfiguration:
    return VehicleConfiguration(
        id=uuid4(),
        identity_hash=uuid4().hex,
        base_identity_hash=uuid4().hex,
        year=year,
        market="US",
        make=make,
        model=model,
        trim=trim,
        engine=engine,
        transmission=transmission,
        drivetrain=None,
        identity_source="workbook",
        verification_status="unverified",
    )


def civic_hx() -> VehicleConfiguration:
    return configuration()


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
    item = civic_hx()
    html = b"""
    <html><body>
      <h1>1998 Honda Civic HX</h1>
      <section>HX 1.6L VTEC-E 4-cylinder engine producing 115 hp.</section>
    </body></html>
    """

    extraction = extract_source("kbb", html, "text/html", item)

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


def test_vtec_e_requires_vtec_e_not_loose_vtec_and_letter_tokens() -> None:
    item = civic_hx()
    html = b"""
    <html><body>
      <h1>1998 Honda Civic HX</h1>
      <section>HX 1.6L VTEC 4-cylinder engine producing 115 hp. Excellent economy.</section>
    </body></html>
    """

    extraction = extract_source("kbb", html, "text/html", item)

    assert "powertrain.engine.technology" not in extraction.field_observations
    assert extraction.matched_fields["engine"] is False


def test_historic_lexus_model_grade_alias_does_not_require_literal_base_word() -> None:
    item = configuration(
        make="Lexus",
        model="ES",
        trim="ES 300 BASE",
        engine="3.0L V6 (200 hp)",
        transmission="4-Speed Automatic",
    )
    html = b"""
    <html><body>
      <h1>1998 Lexus ES 300</h1>
      <section>ES 300 specifications: 3.0L V6, 200 hp, 4-speed automatic.</section>
    </body></html>
    """

    extraction = extract_source("kbb", html, "text/html", item)

    assert extraction.matched_fields["trim"] is True
    assert extraction.field_observations["identity.trim"]["value"] == "ES 300 BASE"


def test_plain_base_trim_is_not_inferred_from_model_name_alone() -> None:
    item = configuration(
        make="Subaru",
        model="FORESTER",
        trim="BASE",
        engine="2.5L Flat-4 (165 hp)",
        transmission="4-Speed Automatic",
    )
    html = b"""
    <html><body>
      <h1>1998 Subaru Forester</h1>
      <section>2.5L flat-4, 165 hp, 4-speed automatic.</section>
    </body></html>
    """

    extraction = extract_source("kbb", html, "text/html", item)

    assert extraction.matched_fields["trim"] is False
    assert "identity.trim" not in extraction.field_observations


def test_numeric_trim_anchors_on_full_trim_phrase() -> None:
    item = configuration(
        make="Subaru",
        model="IMPREZA",
        trim="2.5 RS",
        engine="2.5L Flat-4 (165 hp)",
        transmission="5-Speed Manual",
    )
    html = b"""
    <html><body>
      <p>Other 2.5 liter vehicles are also listed on this page.</p>
      <h2>1998 Subaru Impreza 2.5 RS</h2>
      <section>2.5 RS: 2.5L flat-4, 165 hp, 5-speed manual.</section>
    </body></html>
    """

    extraction = extract_source("motortrend", html, "text/html", item)

    assert extraction.matched_fields["trim"] is True
    assert extraction.field_observations["identity.trim"]["value"] == "2.5 RS"


def test_fueleconomy_model_suffix_can_support_trim_when_explicit() -> None:
    item = civic_hx()
    raw = json.dumps(
        {
            "records": [
                {
                    "year": "1998",
                    "make": "Honda",
                    "model": "Civic HX",
                    "displ": "1.6",
                    "cylinders": "4",
                    "trany": "Automatic variable gear ratios",
                    "drive": "Front-Wheel Drive",
                    "fuelType1": "Regular Gasoline",
                    "city08": "34",
                    "highway08": "40",
                    "comb08": "37",
                }
            ],
            "detail_errors": [],
        }
    ).encode()

    extraction = extract_source("fueleconomy_gov", raw, "application/json", item)

    assert extraction.matched_fields["trim"] is True
    assert extraction.field_observations["identity.trim"]["value"] == "HX"
    assert extraction.field_observations["transmission.family"]["value"] == "CVT"


def test_nhtsa_model_result_supports_model_year_identity_only() -> None:
    item = civic_hx()
    raw = json.dumps(
        {
            "Results": [
                {"Make_Name": "Honda", "Model_Name": "Civic"},
                {"Make_Name": "Honda", "Model_Name": "Accord"},
            ]
        }
    ).encode()

    extraction = extract_source("nhtsa_vpic", raw, "application/json", item)

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
