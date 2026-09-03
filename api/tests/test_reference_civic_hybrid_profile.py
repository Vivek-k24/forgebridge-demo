from fastapi.testclient import TestClient

from partgraph.identity.vehicle.reconciliation import (
    FieldObservation,
    reconcile_field_observations,
)
from partgraph.main import app

VEHICLE_ID = "7feb13e9-bca0-5d8b-b701-f0260cce5da1"


def _field_by_name(payload: dict[str, object], name: str) -> dict[str, object]:
    fields = payload["fields"]
    assert isinstance(fields, list)
    return next(item for item in fields if isinstance(item, dict) and item["field"] == name)


def test_reference_civic_hybrid_workflows() -> None:
    with TestClient(app) as client:
        trims = client.get(
            "/api/v1/vehicle-options/trims",
            params={
                "year": 2009,
                "market": "US",
                "make": "Honda",
                "model": "Civic",
            },
        )
        assert trims.status_code == 200
        assert "HYBRID" in trims.json()

        resolved = client.post(
            "/api/v1/vehicle-selection/resolve",
            json={
                "year": 2009,
                "market": "US",
                "make": "Honda",
                "model": "Civic",
                "trim": "Hybrid",
                "body_style": "Sedan",
                "engine": "1.3L I4 Hybrid",
                "transmission": "CVT",
                "drivetrain": "FWD",
            },
        )
        assert resolved.status_code == 200
        resolution = resolved.json()
        assert resolution["resolution"] == "matched"
        assert len(resolution["matches"]) == 1
        matched = resolution["matches"][0]
        assert matched["id"] == VEHICLE_ID
        assert matched["trim"] == "HYBRID"
        assert matched["body_style"] == "Sedan"
        assert matched["engine"] == "1.3L I4 HYBRID"
        assert matched["transmission"] == "CVT"
        assert matched["drivetrain"] == "FWD"
        assert matched["identity_source"] == "multi_source"
        assert matched["verification_status"] == "verified"

        configuration = client.get(f"/api/v1/vehicle-configurations/{VEHICLE_ID}")
        assert configuration.status_code == 200
        canonical = configuration.json()
        assert canonical["id"] == VEHICLE_ID
        assert canonical["year"] == 2009
        assert canonical["market"] == "US"
        assert canonical["make"] == "Honda"
        assert canonical["model"] == "CIVIC"
        assert canonical["trim"] == "HYBRID"
        assert canonical["generation"] is None
        assert canonical["body_style"] == "Sedan"
        assert canonical["engine"] == "1.3L I4 HYBRID"
        assert canonical["transmission"] == "CVT"
        assert canonical["drivetrain"] == "FWD"

        profile_response = client.get(
            f"/api/v1/vehicle-configurations/{VEHICLE_ID}/profile"
        )
        assert profile_response.status_code == 200
        profile_record = profile_response.json()
        assert profile_record["vehicle_configuration_id"] == VEHICLE_ID
        assert profile_record["verification_status"] == "verified"
        assert profile_record["source_match_count"] >= 3

        profile = profile_record["profile"]
        assert profile["identity"]["trim"] == "HYBRID"
        assert profile["identity"]["body_style"] == "Sedan"
        assert profile["identity"]["drivetrain"] == "FWD"
        assert profile["identity"]["transmission"] == "CVT"
        assert profile["powertrain"]["engine"] == "1.3L I4 HYBRID"
        assert profile["powertrain"]["displacement_cc"] == 1339
        assert profile["powertrain"]["combined_horsepower_hp"] == 110
        assert profile["powertrain"]["combined_torque_lb_ft"] == 123
        assert profile["efficiency"]["epa_city_mpg"] == 40
        assert profile["efficiency"]["epa_highway_mpg"] == 45
        assert profile["efficiency"]["epa_combined_mpg"] == 42
        assert profile["efficiency"]["fuel_tank_gallons"] == 12.3
        assert profile["dimensions_weight"]["curb_weight_lb"] == 2877
        assert profile["dimensions_weight"]["wheelbase_in"] == 106.3
        assert profile["dimensions_weight"]["length_in"] == 177.3
        assert profile["chassis"]["front_suspension"] == "MacPherson strut"
        assert profile["chassis"]["rear_suspension"] == "Multi-link"
        assert profile["chassis"]["tires"] == "P195/65 R15 89S"
        assert profile["manufacturer_service_specifications"][
            "engine_oil_change_with_filter_us_qt"
        ] == 3.4
        assert profile["manufacturer_service_specifications"][
            "transmission_fluid_change_us_qt"
        ] == 3.0

        matrix = profile_record["source_matrix"]
        assert matrix["corroborated_groups"]["core_identity"]["match_count"] >= 3
        assert matrix["corroborated_groups"]["engine_performance"]["match_count"] >= 3
        assert matrix["corroborated_groups"]["dimensions_weight"]["match_count"] >= 3
        conflict = matrix["preserved_conflicts"]["overall_length_in"]
        assert conflict["selected_value"] == 177.3
        assert conflict["conflicting_observation"]["value"] == 176.7

        reconciliation_response = client.get(
            f"/api/v1/vehicle-configurations/{VEHICLE_ID}/profile/reconciliation"
        )
        assert reconciliation_response.status_code == 200
        reconciliation = reconciliation_response.json()
        assert reconciliation["vehicle_configuration_id"] == VEHICLE_ID
        assert reconciliation["observation_records"] == 5
        assert reconciliation["independent_sources"] == 5
        assert reconciliation["rule"]["ordinary_min_independent_sources"] == 3
        assert reconciliation["summary"]["verified_fields"] > 0
        assert reconciliation["summary"]["manufacturer_reported_fields"] == 2

        length = _field_by_name(reconciliation, "dimensions_weight.length_in")
        assert length["status"] == "verified"
        assert length["selected_value"] == 177.3
        assert length["match_count"] == 3
        assert {item["value"] for item in length["conflicts"]} == {176.7, 177.0}

        oil_capacity = _field_by_name(
            reconciliation,
            "manufacturer_service_specifications.engine_oil_change_with_filter_us_qt",
        )
        assert oil_capacity["status"] == "manufacturer_reported"
        assert oil_capacity["selected_value"] == 3.4
        assert oil_capacity["match_count"] == 1

        patch = reconciliation["promotable_profile_patch"]
        assert patch["dimensions_weight"]["length_in"] == 177.3
        assert patch["efficiency"]["epa_combined_mpg"] == 42
        assert patch["manufacturer_service_specifications"][
            "engine_oil_change_with_filter_us_qt"
        ] == 3.4


def test_reconciliation_counts_one_vote_per_independent_source() -> None:
    observations = [
        FieldObservation(
            field="efficiency.epa_city_mpg",
            value=40,
            kind="ordinary",
            source_name="source-a",
            source_class="vehicle_reference",
        ),
        FieldObservation(
            field="efficiency.epa_city_mpg",
            value=40,
            kind="ordinary",
            source_name="source-a",
            source_class="vehicle_reference",
        ),
        FieldObservation(
            field="efficiency.epa_city_mpg",
            value=40,
            kind="ordinary",
            source_name="source-b",
            source_class="vehicle_reference",
        ),
        FieldObservation(
            field="efficiency.epa_city_mpg",
            value=40,
            kind="ordinary",
            source_name="source-c",
            source_class="manufacturer",
        ),
    ]

    result = reconcile_field_observations(observations)
    field = _field_by_name(result, "efficiency.epa_city_mpg")
    assert field["status"] == "verified"
    assert field["match_count"] == 3
    assert field["sources"] == ["source-a", "source-b", "source-c"]


def test_unknown_configuration_has_no_reference_profile() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/vehicle-configurations/00000000-0000-0000-0000-000000000000/profile"
        )
        reconciliation = client.get(
            "/api/v1/vehicle-configurations/00000000-0000-0000-0000-000000000000/"
            "profile/reconciliation"
        )

    assert response.status_code == 404
    assert reconciliation.status_code == 404
