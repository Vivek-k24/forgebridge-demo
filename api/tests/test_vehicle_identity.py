from uuid import uuid4

from fastapi.testclient import TestClient

from partgraph.main import app


def _base_payload(suffix: str) -> dict[str, object]:
    return {
        "year": 2009,
        "market": "US",
        "make": f"Test Make {suffix}",
        "model": "Test Model",
        "generation": "8th",
        "trim": "Hybrid",
    }


def test_vehicle_configuration_persists_and_deduplicates() -> None:
    suffix = uuid4().hex[:8]
    payload = {
        **_base_payload(suffix),
        "body_style": "Sedan",
        "engine": "1.3L",
        "transmission": "CVT",
        "drivetrain": "FWD",
    }
    equivalent = {
        **payload,
        "market": " us ",
        "make": f"  TEST   MAKE {suffix} ",
        "model": "test model",
    }

    with TestClient(app) as client:
        first = client.post("/api/v1/vehicle-configurations", json=payload)
        second = client.post("/api/v1/vehicle-configurations", json=equivalent)

        assert first.status_code == 200
        assert second.status_code == 200

        first_body = first.json()
        second_body = second.json()
        configuration_id = first_body["configuration"]["id"]

        assert first_body["resolution"] == "created"
        assert first_body["created"] is True
        assert second_body["resolution"] == "matched"
        assert second_body["created"] is False
        assert second_body["configuration"]["id"] == configuration_id
        assert first_body["configuration"]["verification_status"] == "unverified"
        assert first_body["configuration"]["identity_source"] == "manual"

        fetched = client.get(f"/api/v1/vehicle-configurations/{configuration_id}")
        listed = client.get("/api/v1/vehicle-configurations?limit=100")

        assert fetched.status_code == 200
        assert fetched.json()["id"] == configuration_id
        assert listed.status_code == 200
        assert configuration_id in {item["id"] for item in listed.json()}


def test_vehicle_configuration_enriches_compatible_partial_identity() -> None:
    suffix = uuid4().hex[:8]
    partial = {
        **_base_payload(suffix),
        "body_style": "4 Dr Sedan",
    }
    detailed = {
        **_base_payload(suffix),
        "body_style": "Sedan",
        "engine": "1.3L",
        "transmission": "CVT",
        "drivetrain": "FWD",
    }

    with TestClient(app) as client:
        first = client.post("/api/v1/vehicle-configurations", json=partial)
        second = client.post("/api/v1/vehicle-configurations", json=detailed)

        assert first.status_code == 200
        assert second.status_code == 200

        first_body = first.json()
        second_body = second.json()
        configuration_id = first_body["configuration"]["id"]

        assert second_body["resolution"] == "enriched"
        assert second_body["configuration"]["id"] == configuration_id
        assert second_body["configuration"]["engine"] == "1.3L"
        assert second_body["configuration"]["transmission"] == "CVT"
        assert second_body["configuration"]["drivetrain"] == "FWD"


def test_vehicle_configuration_requires_more_detail_when_identity_is_ambiguous() -> None:
    suffix = uuid4().hex[:8]
    lx = {
        "year": 2009,
        "market": "US",
        "make": f"Test Make {suffix}",
        "model": "Test Model",
        "trim": "LX",
    }
    ex = {**lx, "trim": "EX"}
    incomplete = {
        "year": 2009,
        "market": "US",
        "make": f"Test Make {suffix}",
        "model": "Test Model",
    }

    with TestClient(app) as client:
        assert client.post("/api/v1/vehicle-configurations", json=lx).status_code == 200
        assert client.post("/api/v1/vehicle-configurations", json=ex).status_code == 200

        ambiguous = client.post("/api/v1/vehicle-configurations", json=incomplete)

        assert ambiguous.status_code == 409
        assert "ambiguous" in ambiguous.json()["detail"]
