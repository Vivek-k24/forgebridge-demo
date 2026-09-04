import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient

from partgraph.database import session_factory
from partgraph.identity.vehicle.schemas import VehicleConfigurationInput
from partgraph.identity.vehicle.service import resolve_configuration
from partgraph.main import app

CSRF = {"X-PartGraph-CSRF": "1"}
PASSWORD = "correct-horse-battery-staple"


def _register(client: TestClient) -> None:
    suffix = uuid4().hex[:12]
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"manual-verify-{suffix}@example.com",
            "username": f"manual_verify_{suffix}"[:32],
            "password": PASSWORD,
        },
        headers=CSRF,
    )
    assert response.status_code == 200, response.text


def _seed_configuration(model: str) -> str:
    async def seed() -> str:
        async with session_factory() as session:
            configuration, _ = await resolve_configuration(
                session,
                VehicleConfigurationInput(
                    year=2008,
                    market="US",
                    make="Honda",
                    model=model,
                    trim="EX",
                    generation="Verification Generation",
                    body_style="Sedan",
                    engine="1.8L I4",
                    transmission="5AT",
                    drivetrain="FWD",
                ),
            )
            return str(configuration.id)

    return asyncio.run(seed())


def test_manual_garage_requires_trim_and_exact_canonical_match() -> None:
    model = f"Verification-{uuid4().hex[:8]}"
    configuration_id = _seed_configuration(model)

    with TestClient(app) as client:
        _register(client)

        missing_trim = client.post(
            "/api/v1/user-vehicles/manual",
            json={
                "selection": {
                    "year": 2008,
                    "market": "US",
                    "make": "Honda",
                    "model": model,
                }
            },
            headers=CSRF,
        )
        assert missing_trim.status_code == 422, missing_trim.text

        wrong_trim = client.post(
            "/api/v1/user-vehicles/manual",
            json={
                "selection": {
                    "year": 2008,
                    "market": "US",
                    "make": "Honda",
                    "model": model,
                    "trim": "Imaginary",
                }
            },
            headers=CSRF,
        )
        assert wrong_trim.status_code == 422, wrong_trim.text
        assert wrong_trim.json()["error"]["code"] == "USER_VEHICLE_IDENTITY_UNVERIFIED"
        assert wrong_trim.json()["error"]["details"]["resolution"] == "manual_candidate"

        exact = client.post(
            "/api/v1/user-vehicles/manual",
            json={
                "nickname": "Verified test car",
                "selection": {
                    "year": 2008,
                    "market": "US",
                    "make": "Honda",
                    "model": model,
                    "trim": "EX",
                },
            },
            headers=CSRF,
        )
        assert exact.status_code == 201, exact.text
        saved = exact.json()
        assert saved["canonical_configuration_id"] == configuration_id
        assert saved["identity_resolution"] == "matched"
        assert saved["identity"]["trim"] == "EX"
        assert saved["identity"]["generation"] == "Verification Generation"


def test_generation_is_an_actual_resolver_constraint() -> None:
    model = f"Generation-{uuid4().hex[:8]}"
    _seed_configuration(model)

    with TestClient(app) as client:
        _register(client)
        wrong_generation = client.post(
            "/api/v1/vehicle-selection/resolve",
            json={
                "year": 2008,
                "market": "US",
                "make": "Honda",
                "model": model,
                "trim": "EX",
                "generation": "Not The Stored Generation",
            },
            headers=CSRF,
        )

    assert wrong_generation.status_code == 200, wrong_generation.text
    assert wrong_generation.json()["resolution"] == "manual_candidate"
    assert wrong_generation.json()["matches"] == []
