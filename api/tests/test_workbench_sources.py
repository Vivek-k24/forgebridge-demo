import json
from uuid import uuid4

from partgraph.identity.vehicle.models import VehicleConfiguration
from partgraph.knowledge.workbench_sources import match_source, source_requests


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


def test_reference_page_requires_configuration_signature_not_just_reachability() -> None:
    configuration = civic_hx()
    html = b"""
    <html><body>
      <h1>1998 Honda Civic HX</h1>
      <section>HX 1.6L VTEC-E 4-cylinder engine with CVT Automatic transmission.</section>
    </body></html>
    """

    matched = match_source("cars_com", html, "text/html", configuration)

    assert matched["year"] is True
    assert matched["make"] is True
    assert matched["model"] is True
    assert matched["trim"] is True
    assert matched["engine"] is True
    assert matched["transmission"] is True
    assert matched["configuration_match"] is True


def test_reference_page_missing_transmission_does_not_vote_for_configuration() -> None:
    configuration = civic_hx()
    html = b"""
    <html><body>
      <h1>1998 Honda Civic HX</h1>
      <section>HX 1.6L VTEC-E 4-cylinder engine.</section>
    </body></html>
    """

    matched = match_source("kbb", html, "text/html", configuration)

    assert matched["engine"] is True
    assert matched["transmission"] is False
    assert matched["configuration_match"] is False


def test_nhtsa_model_result_supports_identity_but_not_trim_powertrain_vote() -> None:
    configuration = civic_hx()
    raw = json.dumps(
        {
            "Results": [
                {"Make_Name": "Honda", "Model_Name": "Civic"},
                {"Make_Name": "Honda", "Model_Name": "Accord"},
            ]
        }
    ).encode()

    matched = match_source("nhtsa_vpic", raw, "application/json", configuration)

    assert matched["year"] is True
    assert matched["make"] is True
    assert matched["model"] is True
    assert matched["configuration_match"] is False


def test_workbench_attempts_up_to_five_independent_references() -> None:
    providers = [provider for provider, _ in source_requests(civic_hx())]

    assert providers == ["nhtsa_vpic", "cars_com", "edmunds", "kbb", "motortrend"]
