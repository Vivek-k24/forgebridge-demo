from uuid import uuid4

from fastapi.testclient import TestClient

from partgraph.main import app


def test_vehicle_configuration_enriches_equivalent_identity() -> None:
    suffix = uuid4().hex[:8]
    first_payload = {
        "year": 2009,
        "market": "US",
        "make": "honda",
        "model": f"Civic {suffix}",
        "generation": "8th gen",
        "trim": "Hybrid",
        "body_style": "4 Dr Sedan",
    }
    richer_payload = {
        "year": 2009,
        "market": "United States of America",
        "make": " HONDA ",
        "model": f"civic-{suffix}",
        "generation": "eighth generation",
        "trim": "HYBRID",
        "body_style": "four-door sedan",
        "engine": "hybrid inline-4 1.3 liter",
        "transmission": "continuously variable transmission",
        "drivetrain": "front wheel drive",
    }

    with TestClient(app) as client:
        first = client.post("/api/v1/vehicle-configurations", json=first_payload)
        second = client.post("/api/v1/vehicle-configurations", json=richer_payload)

        assert first.status_code == 200
        assert second.status_code == 200

        first_body = first.json()
        second_body = second.json()
        configuration_id = first_body["configuration"]["id"]

        assert first_body["resolution"] == "created"
        assert second_body["resolution"] == "enriched"
        assert second_body["configuration"]["id"] == configuration_id
        assert second_body["configuration"]["market"] == "US"
        assert second_body["configuration"]["make"] == "Honda"
        assert second_body["configuration"]["body_style"] == "Sedan"
        assert second_body["configuration"]["engine"] == "1.3L I4 HYBRID"
        assert second_body["configuration"]["transmission"] == "CVT"
        assert second_body["configuration"]["drivetrain"] == "FWD"
        assert second_body["configuration"]["verification_status"] == "unverified"

        third = client.post(
            "/api/v1/vehicle-configurations",
            json={
                **richer_payload,
                "market": "U.S.A.",
                "body_style": "Sedan",
                "engine": "1.3L I4 hybrid",
                "transmission": "CVT",
                "drivetrain": "FWD",
            },
        )
        assert third.status_code == 200
        assert third.json()["resolution"] == "matched"
        assert third.json()["configuration"]["id"] == configuration_id


def test_vehicle_identity_is_not_honda_specific() -> None:
    suffix = uuid4().hex[:8]
    first_payload = {
        "year": 2020,
        "market": "USA",
        "make": "Chevy",
        "model": f"Silverado-1500-{suffix}",
        "trim": "LT",
        "body_style": "pickup truck",
        "transmission": "automatic transmission",
        "drivetrain": "4x4",
    }
    equivalent_payload = {
        **first_payload,
        "market": "United States",
        "make": "Chevrolet",
        "model": f"silverado 1500 {suffix}",
        "body_style": "truck",
        "transmission": "AT",
        "drivetrain": "four wheel drive",
    }

    with TestClient(app) as client:
        first = client.post("/api/v1/vehicle-configurations", json=first_payload)
        second = client.post("/api/v1/vehicle-configurations", json=equivalent_payload)

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["resolution"] == "created"
        assert second.json()["resolution"] == "matched"
        assert first.json()["configuration"]["id"] == second.json()["configuration"]["id"]
        assert second.json()["configuration"]["make"] == "Chevrolet"
        assert second.json()["configuration"]["body_style"] == "Pickup"
        assert second.json()["configuration"]["drivetrain"] == "4WD"


def test_incomplete_identity_is_rejected_when_multiple_variants_fit() -> None:
    suffix = uuid4().hex[:8]
    base = {
        "year": 2021,
        "market": "Canada",
        "make": "Toyota",
        "model": f"Corolla {suffix}",
        "body_style": "Sedan",
    }

    with TestClient(app) as client:
        le = client.post(
            "/api/v1/vehicle-configurations",
            json={**base, "trim": "LE"},
        )
        xle = client.post(
            "/api/v1/vehicle-configurations",
            json={**base, "trim": "XLE"},
        )
        ambiguous = client.post("/api/v1/vehicle-configurations", json=base)

        assert le.status_code == 200
        assert xle.status_code == 200
        assert le.json()["configuration"]["id"] != xle.json()["configuration"]["id"]
        assert ambiguous.status_code == 409
        assert "Multiple stored configurations" in ambiguous.json()["detail"]


def test_brand_registry_is_served_by_api() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/vehicle-brands")

    assert response.status_code == 200
    brands = {item["name"]: item["status"] for item in response.json()}
    assert brands["Honda"] == "active"
    assert brands["Toyota"] == "active"
    assert brands["Lexus"] == "active"
    assert brands["Acura"] == "active"
    assert brands["Genesis"] == "active"
    assert brands["Pontiac"] == "legacy"
    assert "BMW" not in brands
