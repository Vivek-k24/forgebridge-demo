import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient

from partgraph.database import session_factory
from partgraph.main import app
from partgraph.vehicle.schemas import VehicleConfigurationInput
from partgraph.vehicle.service import resolve_configuration


def seed_configuration(payload: dict[str, object]) -> str:
    async def seed() -> str:
        async with session_factory() as session:
            configuration, _ = await resolve_configuration(
                session,
                VehicleConfigurationInput.model_validate(payload),
            )
            return str(configuration.id)

    return asyncio.run(seed())


def test_public_api_does_not_create_canonical_vehicle_truth() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/vehicle-configurations",
            json={
                "year": 2009,
                "market": "US",
                "make": "Honda",
                "model": "Civic",
                "trim": "Hybrid",
            },
        )

    assert response.status_code == 405


def test_vehicle_options_are_read_from_known_canonical_rows() -> None:
    suffix = uuid4().hex[:8]
    model = f"Civic-{suffix}"
    seed_configuration(
        {
            "year": 2009,
            "market": "US",
            "make": "Honda",
            "model": model,
            "generation": "8th gen",
            "trim": "Hybrid",
            "body_style": "Sedan",
            "engine": "1.3L I4 Hybrid",
            "transmission": "CVT",
            "drivetrain": "FWD",
        }
    )
    seed_configuration(
        {
            "year": 2009,
            "market": "US",
            "make": "Honda",
            "model": model,
            "generation": "8th gen",
            "trim": "EX",
            "body_style": "Sedan",
            "engine": "1.8L I4",
            "transmission": "5AT",
            "drivetrain": "FWD",
        }
    )

    with TestClient(app) as client:
        models = client.get(
            "/api/v1/vehicle-options/models",
            params={"year": 2009, "market": "USA", "make": "honda", "q": suffix},
        )
        trims = client.get(
            "/api/v1/vehicle-options/trims",
            params={
                "year": 2009,
                "market": "US",
                "make": "Honda",
                "model": model.replace("-", " "),
            },
        )
        generations = client.get(
            "/api/v1/vehicle-options/generations",
            params={
                "year": 2009,
                "market": "US",
                "make": "Honda",
                "model": model,
                "trim": "Hybrid",
            },
        )

    assert models.status_code == 200
    assert model.upper() in models.json()
    assert trims.status_code == 200
    assert trims.json() == ["EX", "HYBRID"]
    assert generations.status_code == 200
    assert generations.json() == ["8"]


def test_selection_resolves_known_trim_without_using_generation() -> None:
    suffix = uuid4().hex[:8]
    model = f"Corolla-{suffix}"
    configuration_id = seed_configuration(
        {
            "year": 2021,
            "market": "Canada",
            "make": "Toyota",
            "model": model,
            "generation": "12th",
            "trim": "LE",
            "body_style": "Sedan",
        }
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/vehicle-selection/resolve",
            json={
                "year": 2021,
                "market": "CA",
                "make": "toyota",
                "model": model.replace("-", " ").lower(),
                "trim": "le",
                "generation": "99th generation",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["resolution"] == "matched"
    assert body["matches"][0]["id"] == configuration_id
    assert body["normalized"]["market"] == "CA"
    assert body["normalized"]["make"] == "Toyota"
    assert body["normalized"]["generation"] == "99"


def test_selection_surfaces_ambiguity_instead_of_guessing() -> None:
    suffix = uuid4().hex[:8]
    model = f"Accord-{suffix}"
    for trim in ("LX", "EX"):
        seed_configuration(
            {
                "year": 2018,
                "market": "US",
                "make": "Honda",
                "model": model,
                "trim": trim,
                "body_style": "Sedan",
            }
        )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/vehicle-selection/resolve",
            json={
                "year": 2018,
                "market": "US",
                "make": "Honda",
                "model": model,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["resolution"] == "ambiguous"
    assert len(body["matches"]) == 2


def test_unknown_manual_text_is_candidate_only_and_does_not_write_canonical_db() -> None:
    suffix = uuid4().hex[:8]
    unknown_model = f"Garage-Special-{suffix}"

    with TestClient(app) as client:
        before = client.get(
            "/api/v1/vehicle-options/models",
            params={"year": 2015, "market": "US", "make": "Ford", "q": suffix},
        )
        resolved = client.post(
            "/api/v1/vehicle-selection/resolve",
            json={
                "year": 2015,
                "market": "US",
                "make": "Ford",
                "model": unknown_model,
                "trim": "Home Garage",
            },
        )
        after = client.get(
            "/api/v1/vehicle-options/models",
            params={"year": 2015, "market": "US", "make": "Ford", "q": suffix},
        )

    assert before.status_code == 200
    assert before.json() == []
    assert resolved.status_code == 200
    assert resolved.json()["resolution"] == "manual_candidate"
    assert resolved.json()["matches"] == []
    assert after.status_code == 200
    assert after.json() == []


def test_selection_year_policy_is_enforced() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/vehicle-options/models",
            params={"year": 1995, "market": "US", "make": "Honda"},
        )

    assert response.status_code == 422
    assert "1996" in response.json()["detail"]


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
    assert brands["Volkswagen"] == "active"
    assert brands["Volvo"] == "active"
    assert brands["Isuzu"] == "legacy"
    assert "Tesla" not in brands
    assert "BMW" not in brands
