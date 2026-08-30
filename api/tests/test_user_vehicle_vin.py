import asyncio
import base64
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select, text, update

import partgraph.identity.user_vehicle.crypto as vin_crypto
import partgraph.identity.user_vehicle.service as user_vehicle_service
from partgraph.database import session_factory
from partgraph.errors import ErrorCode, PartGraphError
from partgraph.identity.auth.service import set_user_context
from partgraph.identity.user_vehicle.crypto import VinCryptoError, reveal_vin
from partgraph.identity.user_vehicle.models import UserVehicle, VinDecodeCache
from partgraph.identity.user_vehicle.vin import ProviderIdentity, parse_nhtsa_payload, validate_vin
from partgraph.identity.vehicle.schemas import VehicleConfigurationInput
from partgraph.identity.vehicle.service import resolve_configuration
from partgraph.main import app

CSRF = {"X-PartGraph-CSRF": "1"}
PASSWORD = "correct-horse-battery-staple"
VALID_VIN = "1HGCM82633A004352"


@pytest.fixture(autouse=True)
def _test_vin_protection(monkeypatch: pytest.MonkeyPatch) -> None:
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


def _register(client: TestClient, prefix: str) -> str:
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
    return response.json()["user"]["id"]


def _error(response) -> dict[str, object]:
    payload = response.json()
    assert set(payload) == {"error"}
    error = payload["error"]
    assert isinstance(error["code"], str)
    assert isinstance(error["message"], str)
    assert isinstance(error["request_id"], str)
    assert isinstance(error["retryable"], bool)
    return error


def _seed_configuration(*, model: str, trim: str | None = "EX") -> str:
    async def seed() -> str:
        async with session_factory() as session:
            configuration, _ = await resolve_configuration(
                session,
                VehicleConfigurationInput(
                    year=2003,
                    market="US",
                    make="Honda",
                    model=model,
                    trim=trim,
                    body_style="Sedan",
                    engine="3.0L V6",
                    transmission="5AT",
                    drivetrain="FWD",
                ),
            )
            return str(configuration.id)

    return asyncio.run(seed())


def _provider(model: str, *, trim: str | None = "EX") -> ProviderIdentity:
    return ProviderIdentity(
        year=2003,
        make="Honda",
        model=model,
        trim=trim,
        body_style="Sedan",
        engine="3.0L V6",
        transmission="5-speed Automatic",
        drivetrain="FWD",
    )


def test_vin_format_and_check_digit_are_rejected_before_provider() -> None:
    assert validate_vin(VALID_VIN) == VALID_VIN

    with pytest.raises(PartGraphError) as invalid_format:
        validate_vin("1HGCM82633A00I352")
    assert invalid_format.value.code == ErrorCode.VIN_INVALID_FORMAT

    bad_check_digit = f"{VALID_VIN[:8]}4{VALID_VIN[9:]}"
    with pytest.raises(PartGraphError) as invalid_digit:
        validate_vin(bad_check_digit)
    assert invalid_digit.value.code == ErrorCode.VIN_INVALID_CHECK_DIGIT


def test_nhtsa_payload_is_normalized_without_fabricating_unknown_fields() -> None:
    provider = parse_nhtsa_payload(
        {
            "Results": [
                {
                    "ErrorCode": "0",
                    "ModelYear": "2003",
                    "Make": "HONDA",
                    "Model": "Accord",
                    "Trim": "",
                    "BodyClass": "Sedan/Saloon",
                    "DisplacementL": "3",
                    "EngineCylinders": "6",
                    "TransmissionStyle": "Automatic",
                    "TransmissionSpeeds": "5",
                    "DriveType": "FWD/Front-Wheel Drive",
                }
            ]
        }
    )

    assert provider == ProviderIdentity(
        year=2003,
        make="HONDA",
        model="Accord",
        trim=None,
        body_style="Sedan/Saloon",
        engine="3L 6-cylinder",
        transmission="5-speed Automatic",
        drivetrain="FWD/Front-Wheel Drive",
    )


def test_vin_decode_is_cached_per_owner_and_re_resolved_without_second_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = f"Accord-{uuid4().hex[:8]}"
    configuration_id = _seed_configuration(model=model)
    calls = 0

    async def fake_decoder(_: str) -> ProviderIdentity:
        nonlocal calls
        calls += 1
        return _provider(model)

    monkeypatch.setattr(user_vehicle_service, "decode_vin_values_extended", fake_decoder)

    with TestClient(app) as client:
        _register(client, "cache_owner")
        first = client.post(
            "/api/v1/user-vehicles/vin/decode",
            json={"market": "US", "vin": VALID_VIN},
            headers=CSRF,
        )
        second = client.post(
            "/api/v1/user-vehicles/vin/decode",
            json={"market": "US", "vin": VALID_VIN},
            headers=CSRF,
        )

    assert first.status_code == second.status_code == 200
    assert first.json()["source"] == "provider"
    assert second.json()["source"] == "cache"
    assert first.json()["canonical_matches"][0]["id"] == configuration_id
    assert second.json()["canonical_matches"][0]["id"] == configuration_id
    assert calls == 1
    assert VALID_VIN not in first.text
    assert VALID_VIN not in second.text


def test_vin_storage_is_encrypted_owner_bound_and_duplicate_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = f"Accord-{uuid4().hex[:8]}"
    _seed_configuration(model=model)

    async def fake_decoder(_: str) -> ProviderIdentity:
        return _provider(model)

    monkeypatch.setattr(user_vehicle_service, "decode_vin_values_extended", fake_decoder)

    with TestClient(app) as client_a, TestClient(app) as client_b:
        user_a = UUID(_register(client_a, "vin_a"))
        user_b = UUID(_register(client_b, "vin_b"))

        first = client_a.post(
            "/api/v1/user-vehicles/vin",
            json={"market": "US", "vin": VALID_VIN, "nickname": "Primary"},
            headers=CSRF,
        )
        duplicate = client_a.post(
            "/api/v1/user-vehicles/vin",
            json={"market": "US", "vin": VALID_VIN},
            headers=CSRF,
        )
        other_owner = client_b.post(
            "/api/v1/user-vehicles/vin",
            json={"market": "US", "vin": VALID_VIN},
            headers=CSRF,
        )

    assert first.status_code == 201, first.text
    assert duplicate.status_code == 409
    assert _error(duplicate)["code"] == ErrorCode.USER_VEHICLE_VIN_EXISTS
    assert other_owner.status_code == 201
    assert first.json()["vin_masked"] == "***********004352"
    assert VALID_VIN not in first.text

    async def verify_storage() -> None:
        async with session_factory() as session:
            rows = list(
                await session.scalars(
                    select(UserVehicle).where(UserVehicle.user_id.in_([user_a, user_b]))
                )
            )
            assert len(rows) == 2
            for row in rows:
                assert row.vin_ciphertext is not None
                assert row.vin_nonce is not None
                assert row.vin_key_version == 1
                assert row.vin_fingerprint is not None
                assert row.vin_last6 == "004352"
                assert VALID_VIN.encode() not in row.vin_ciphertext
                assert reveal_vin(
                    user_id=row.user_id,
                    ciphertext=row.vin_ciphertext,
                    nonce=row.vin_nonce,
                    key_version=row.vin_key_version,
                ) == VALID_VIN
            assert rows[0].vin_fingerprint == rows[1].vin_fingerprint

    asyncio.run(verify_storage())


def test_rls_blocks_cross_user_vehicle_and_cache_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = f"Accord-{uuid4().hex[:8]}"
    _seed_configuration(model=model)

    async def fake_decoder(_: str) -> ProviderIdentity:
        return _provider(model)

    monkeypatch.setattr(user_vehicle_service, "decode_vin_values_extended", fake_decoder)

    with TestClient(app) as client_a, TestClient(app) as client_b:
        user_a = _register(client_a, "rls_vehicle_a")
        user_b = _register(client_b, "rls_vehicle_b")
        created = client_b.post(
            "/api/v1/user-vehicles/vin",
            json={"market": "US", "vin": VALID_VIN},
            headers=CSRF,
        )
        assert created.status_code == 201
        vehicle_id = created.json()["id"]

        hidden = client_a.get(f"/api/v1/user-vehicles/{vehicle_id}")
        assert hidden.status_code == 404

        client_a.post(
            "/api/v1/user-vehicles/vin/decode",
            json={"market": "US", "vin": VALID_VIN},
            headers=CSRF,
        )

    async def attempt_cross_owner_writes() -> tuple[int, int]:
        async with session_factory() as session:
            async with session.begin():
                await session.execute(text("SET LOCAL ROLE partgraph_app"))
                await set_user_context(session, UUID(user_a))
                vehicle_result = await session.execute(
                    update(UserVehicle)
                    .where(UserVehicle.id == UUID(vehicle_id))
                    .values(nickname="forbidden")
                )
                cache_result = await session.execute(
                    update(VinDecodeCache)
                    .where(VinDecodeCache.user_id == UUID(user_b))
                    .values(identity_resolution="manual_candidate")
                )
                return vehicle_result.rowcount, cache_result.rowcount

    assert asyncio.run(attempt_cross_owner_writes()) == (0, 0)


def test_expired_cache_calls_provider_again(monkeypatch: pytest.MonkeyPatch) -> None:
    model = f"Accord-{uuid4().hex[:8]}"
    _seed_configuration(model=model)
    calls = 0

    async def fake_decoder(_: str) -> ProviderIdentity:
        nonlocal calls
        calls += 1
        return _provider(model)

    monkeypatch.setattr(user_vehicle_service, "decode_vin_values_extended", fake_decoder)

    with TestClient(app) as client:
        user_id = _register(client, "expiry")
        first = client.post(
            "/api/v1/user-vehicles/vin/decode",
            json={"market": "US", "vin": VALID_VIN},
            headers=CSRF,
        )
        assert first.status_code == 200

        async def expire() -> None:
            async with session_factory() as session:
                async with session.begin():
                    await session.execute(
                        update(VinDecodeCache)
                        .where(VinDecodeCache.user_id == UUID(user_id))
                        .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
                    )

        asyncio.run(expire())
        second = client.post(
            "/api/v1/user-vehicles/vin/decode",
            json={"market": "US", "vin": VALID_VIN},
            headers=CSRF,
        )

    assert second.status_code == 200
    assert second.json()["source"] == "provider"
    assert calls == 2


def test_ambiguous_and_manual_candidate_vin_results_never_create_canonical_truth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ambiguous_model = f"Accord-{uuid4().hex[:8]}"
    _seed_configuration(model=ambiguous_model, trim="EX")
    _seed_configuration(model=ambiguous_model, trim="LX")

    async def ambiguous_decoder(_: str) -> ProviderIdentity:
        return _provider(ambiguous_model, trim=None)

    monkeypatch.setattr(user_vehicle_service, "decode_vin_values_extended", ambiguous_decoder)
    with TestClient(app) as client:
        _register(client, "ambiguous")
        ambiguous = client.post(
            "/api/v1/user-vehicles/vin/decode",
            json={"market": "US", "vin": VALID_VIN},
            headers=CSRF,
        )
    assert ambiguous.status_code == 200
    assert ambiguous.json()["resolution"] == "ambiguous"
    assert len(ambiguous.json()["canonical_matches"]) == 2

    manual_model = f"Unknown-{uuid4().hex[:8]}"

    async def manual_decoder(_: str) -> ProviderIdentity:
        return _provider(manual_model)

    monkeypatch.setattr(user_vehicle_service, "decode_vin_values_extended", manual_decoder)
    with TestClient(app) as client:
        _register(client, "manual_candidate")
        manual = client.post(
            "/api/v1/user-vehicles/vin/decode",
            json={"market": "US", "vin": "1M8GDM9AXKP042788"},
            headers=CSRF,
        )
    assert manual.status_code == 200
    assert manual.json()["resolution"] == "manual_candidate"
    assert manual.json()["canonical_matches"] == []


def test_provider_timeout_unsupported_vehicle_and_private_payload_limit_have_stable_codes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def timeout_decoder(_: str) -> ProviderIdentity:
        raise PartGraphError(
            code=ErrorCode.VIN_PROVIDER_TIMEOUT,
            message="VIN decoder timed out. Use vehicle details or try again.",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            retryable=True,
        )

    monkeypatch.setattr(user_vehicle_service, "decode_vin_values_extended", timeout_decoder)
    with TestClient(app) as client:
        _register(client, "provider_timeout")
        timeout = client.post(
            "/api/v1/user-vehicles/vin/decode",
            json={"market": "US", "vin": VALID_VIN},
            headers=CSRF,
        )
        assert timeout.status_code == 504
        assert _error(timeout)["code"] == ErrorCode.VIN_PROVIDER_TIMEOUT

        too_large = client.post(
            "/api/v1/user-vehicles/vin/decode",
            content=b"x" * (32 * 1024 + 1),
            headers={**CSRF, "Content-Type": "application/json"},
        )
        assert too_large.status_code == 413
        assert _error(too_large)["code"] == ErrorCode.REQUEST_PAYLOAD_TOO_LARGE

    model = f"Future-{uuid4().hex[:8]}"

    async def unsupported_decoder(_: str) -> ProviderIdentity:
        return ProviderIdentity(
            year=2101,
            make="Honda",
            model=model,
            trim=None,
            body_style=None,
            engine=None,
            transmission=None,
            drivetrain=None,
        )

    monkeypatch.setattr(user_vehicle_service, "decode_vin_values_extended", unsupported_decoder)
    with TestClient(app) as client:
        _register(client, "unsupported_vin")
        unsupported = client.post(
            "/api/v1/user-vehicles/vin/decode",
            json={"market": "US", "vin": VALID_VIN},
            headers=CSRF,
        )
    assert unsupported.status_code == 422
    assert _error(unsupported)["code"] == ErrorCode.VEHICLE_UNSUPPORTED_YEAR


def test_malformed_vin_key_configuration_fails_closed() -> None:
    vin_crypto.settings = SimpleNamespace(
        vin_encryption_keys="not-json",
        vin_active_key_version=1,
        vin_lookup_key="not-a-key",
    )
    with pytest.raises(VinCryptoError):
        reveal_vin(
            user_id=uuid4(),
            ciphertext=b"ciphertext",
            nonce=b"0" * 12,
            key_version=1,
        )
