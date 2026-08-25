from uuid import uuid4

from fastapi.testclient import TestClient

from partgraph.main import app


def test_vehicle_configuration_persists_and_deduplicates() -> None:
    suffix = uuid4().hex[:8]
    payload = {
        "year": 2009,
        "market": "US",
        "make": f"Test Make {suffix}",
        "model": "Test Model",
        "generation": "8th",
        "trim": "Hybrid",
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

        assert first_body["created"] is True
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
