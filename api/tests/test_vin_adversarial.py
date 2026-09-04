import asyncio
import base64
import json
from types import SimpleNamespace
from urllib.error import HTTPError
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import partgraph.identity.user_vehicle.crypto as vin_crypto
import partgraph.identity.user_vehicle.service as user_vehicle_service
import partgraph.identity.user_vehicle.vin as vin_provider
from partgraph.database import session_factory
from partgraph.errors import ErrorCode, PartGraphError
from partgraph.identity.auth.service import set_user_context
from partgraph.identity.user_vehicle.schemas import VinUserVehicleCreate
from partgraph.identity.user_vehicle.service import create_vin_user_vehicle
from partgraph.identity.user_vehicle.vin import ProviderIdentity
from partgraph.main import app

CSRF = {"X-PartGraph-CSRF": "1"}
PASSWORD = "correct-horse-battery-staple"
VALID_VIN = "1HGCM82633A004352"


@pytest.fixture(autouse=True)
def _vin_test_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    encryption_key = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
    lookup_key = base64.urlsafe_b64encode(bytes(reversed(range(32)))).decode("ascii")
    monkeypatch.setattr(
        vin_crypto,
        "settings",
        SimpleNamespace(
            vin_encryption_keys=json.dumps({"1": encryption_key}),
            vin_active_key_version=1,
            vin_lookup_key=lookup_key,
        ),
    )
    monkeypatch.setattr(
        user_vehicle_service,
        "settings",
        SimpleNamespace(vin_cache_hours=24),
    )


def _register(client: TestClient, prefix: str) -> UUID:
    suffix = uuid4().hex[:12]
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"{prefix}-{suffix}@example.com",
            "username": f"{prefix}_{suffix}"[:32],
            "password": PASSWORD,
        },
        headers=CSRF,
    )
    assert response.status_code == 200, response.text
    return UUID(response.json()["user"]["id"])


def test_missing_vin_keys_fail_closed_before_provider_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        vin_crypto,
        "settings",
        SimpleNamespace(
            vin_encryption_keys="",
            vin_active_key_version=1,
            vin_lookup_key="",
        ),
    )
    provider_called = False

    async def unexpected_provider(_: str) -> ProviderIdentity:
        nonlocal provider_called
        provider_called = True
        raise AssertionError("provider must not run before protected VIN storage is available")

    monkeypatch.setattr(user_vehicle_service, "decode_vin_values_extended", unexpected_provider)

    with TestClient(app) as client:
        _register(client, "missing_keys")
        response = client.post(
            "/api/v1/user-vehicles/vin",
            json={"market": "US", "vin": VALID_VIN},
            headers=CSRF,
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "VIN_CRYPTO_UNAVAILABLE"
    assert VALID_VIN not in response.text
    assert provider_called is False


def test_nhtsa_http_failure_is_normalized_without_vin_leak(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        vin_provider,
        "settings",
        SimpleNamespace(
            nhtsa_base_url="https://vpic.example.invalid/api/vehicles",
            nhtsa_timeout_seconds=1.0,
        ),
    )

    def fail_http(request, timeout):  # noqa: ANN001
        raise HTTPError(
            url=f"https://vpic.example.invalid/{VALID_VIN}",
            code=500,
            msg="upstream failure",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(vin_provider, "urlopen", fail_http)

    with pytest.raises(PartGraphError) as failure:
        vin_provider._fetch_sync(VALID_VIN)

    assert failure.value.code == ErrorCode.VIN_PROVIDER_UNAVAILABLE
    assert failure.value.status_code == 503
    assert failure.value.retryable is True
    assert VALID_VIN not in str(failure.value)


def test_same_owner_vin_race_creates_exactly_one_vehicle(monkeypatch: pytest.MonkeyPatch) -> None:
    model = f"Race-{uuid4().hex[:8]}"

    async def fake_decoder(_: str) -> ProviderIdentity:
        await asyncio.sleep(0.02)
        return ProviderIdentity(
            year=2003,
            make="Honda",
            model=model,
            trim="EX",
            body_style="Sedan",
            engine="3.0L V6",
            transmission="5-speed Automatic",
            drivetrain="FWD",
        )

    monkeypatch.setattr(user_vehicle_service, "decode_vin_values_extended", fake_decoder)

    with TestClient(app) as client:
        user_id = _register(client, "vin_race")

    payload = VinUserVehicleCreate(market="US", vin=VALID_VIN, nickname="Race car")

    async def attempt() -> tuple[str, str | None]:
        async with session_factory() as session:
            async with session.begin():
                await session.execute(text("SET LOCAL ROLE partgraph_app"))
                await set_user_context(session, user_id)
                try:
                    vehicle = await create_vin_user_vehicle(
                        session,
                        user_id=user_id,
                        payload=payload,
                    )
                except PartGraphError as exc:
                    return str(exc.code), None
                return "created", str(vehicle.id)

    async def race() -> list[tuple[str, str | None]]:
        return list(await asyncio.gather(attempt(), attempt()))

    results = asyncio.run(race())
    statuses = sorted(result[0] for result in results)
    created_ids = [result[1] for result in results if result[0] == "created"]

    assert statuses == ["USER_VEHICLE_VIN_EXISTS", "created"]
    assert len(created_ids) == 1

    async def count_rows() -> int:
        async with session_factory() as session:
            async with session.begin():
                await session.execute(text("SET LOCAL ROLE partgraph_app"))
                await set_user_context(session, user_id)
                return int(
                    await session.scalar(
                        text(
                            "SELECT count(*) FROM user_vehicles "
                            "WHERE user_id = :user_id AND vin_fingerprint IS NOT NULL"
                        ),
                        {"user_id": user_id},
                    )
                )

    assert asyncio.run(count_rows()) == 1
