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
    assert invalid_digit.value.code == ErrorCode.VIN_CHECK_DIGIT_INVALID


def test_nhtsa_parser_rejects_malformed_and_decode_error_payloads_without_vin_echo() -> None:
    with pytest.raises(PartGraphError) as malformed:
        parse_nhtsa_payload({"Results": []})
    assert malformed.value.code == ErrorCode.VIN_PROVIDER_INVALID_RESPONSE
    assert VALID_VIN not in str(malformed.value)

    with pytest.raises(PartGraphError) as decode_error:
        parse_nhtsa_payload(
            {
                "Results": [
                    {
                        "ErrorCode": "1,14",
                        "ModelYear": "2003",
                        "Make": "Honda",
                        "Model": "Accord",
                    }
                ]
            }
        )
    assert decode_error.value.code == ErrorCode.VIN_DECODE_FAILED
    assert VALID_VIN not in str(decode_error.value)


def test_manual_vehicle_is_private_and_archive_preserves_history() -> None:
    model = f"Accord-{uuid4().hex[:8]}"
    configuration_id = _seed_configuration(model=model)

    with TestClient(app) as owner, TestClient(app) as stranger:
        _register(owner, "manual_owner")
        _register(stranger, "manual_other")
        created = owner.post(
            "/api/v1/user-vehicles/manual",
            json={
                "nickname": "Daily car",
                "selection": {
                    "year": 2003,
                    "market": "US",
                    "make": "Honda",
                    "model": model,
                    "trim": "EX",
                },
            },
            headers=CSRF,
        )
        assert created.status_code == 201, created.text
        vehicle = created.json()
        assert vehicle["canonical_configuration_id"] == configuration_id
        assert vehicle["identity_source"] == "manual"
        assert vehicle["identity_resolution"] == "matched"

        stranger_read = stranger.get(f"/api/v1/user-vehicles/{vehicle['id']}")
        assert stranger_read.status_code == 404
        assert _error(stranger_read)["code"] == "USER_VEHICLE_NOT_FOUND"

        stranger_archive = stranger.patch(
            f"/api/v1/user-vehicles/{vehicle['id']}/archive",
            headers=CSRF,
        )
        assert stranger_archive.status_code == 404
        assert _error(stranger_archive)["code"] == "USER_VEHICLE_NOT_FOUND"

        archived = owner.patch(
            f"/api/v1/user-vehicles/{vehicle['id']}/archive",
            headers=CSRF,
        )
        assert archived.status_code == 200
        assert archived.json()["archived_at"] is not None

        active = owner.get("/api/v1/user-vehicles")
        history = owner.get("/api/v1/user-vehicles?include_archived=true")
        assert active.status_code == history.status_code == 200
        assert all(item["id"] != vehicle["id"] for item in active.json())
        assert any(item["id"] == vehicle["id"] for item in history.json())

        hard_delete = owner.delete(f"/api/v1/user-vehicles/{vehicle['id']}")
        assert hard_delete.status_code == 405
        assert _error(hard_delete)["code"] == "REQUEST_METHOD_NOT_ALLOWED"


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
    assert first.json()["matches"][0]["id"] == configuration_id
    assert second.json()["matches"][0]["id"] == configuration_id
    assert first.json()["masked_vin"] == "***********004352"
    assert VALID_VIN not in first.text
    assert calls == 1


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
    assert _error(duplicate)["code"] == "USER_VEHICLE_VIN_EXISTS"
    assert other_owner.status_code == 201, other_owner.text
    assert VALID_VIN not in first.text
    assert VALID_VIN not in other_owner.text

    async def inspect() -> None:
        async with session_factory() as session:
            row_a = await session.get(UserVehicle, UUID(first.json()["id"]))
            row_b = await session.get(UserVehicle, UUID(other_owner.json()["id"]))
            assert row_a is not None and row_b is not None
            assert row_a.vin_ciphertext is not None
            assert row_a.vin_nonce is not None
            assert row_a.vin_key_version is not None
            assert VALID_VIN.encode() not in row_a.vin_ciphertext
            assert row_a.vin_fingerprint != row_b.vin_fingerprint
            assert row_a.vin_last6 == row_b.vin_last6 == "004352"
            assert reveal_vin(
                ciphertext=row_a.vin_ciphertext,
                nonce=row_a.vin_nonce,
                key_version=row_a.vin_key_version,
                user_id=user_a,
            ) == VALID_VIN
            with pytest.raises(VinCryptoError):
                reveal_vin(
                    ciphertext=row_a.vin_ciphertext,
                    nonce=row_a.vin_nonce,
                    key_version=row_a.vin_key_version,
                    user_id=user_b,
                )

    asyncio.run(inspect())


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
        vehicle_b = created.json()["id"]

    async def scenario() -> None:
        async with session_factory() as session:
            async with session.begin():
                await session.execute(text("SET LOCAL ROLE partgraph_app"))
                await set_user_context(session, user_a)

                other_vehicle = await session.get(UserVehicle, UUID(vehicle_b))
                assert other_vehicle is None

                other_cache = (
                    await session.execute(
                        select(VinDecodeCache).where(VinDecodeCache.user_id == user_b)
                    )
                ).scalars().first()
                assert other_cache is None

                updated = await session.execute(
                    update(UserVehicle)
                    .where(UserVehicle.id == vehicle_b)
                    .values(archived_at=datetime.now(UTC))
                )
                assert updated.rowcount == 0

    asyncio.run(scenario())


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
                        .where(VinDecodeCache.user_id == user_id)
                        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
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
    assert len(ambiguous.json()["matches"]) == 2

    unknown_model = f"Unknown-{uuid4().hex[:8]}"

    async def unknown_decoder(_: str) -> ProviderIdentity:
        return _provider(unknown_model)

    monkeypatch.setattr(user_vehicle_service, "decode_vin_values_extended", unknown_decoder)
    with TestClient(app) as client:
        _register(client, "candidate")
        candidate = client.post(
            "/api/v1/user-vehicles/vin",
            json={"market": "US", "vin": VALID_VIN},
            headers=CSRF,
        )
    assert candidate.status_code == 201, candidate.text
    assert candidate.json()["identity_resolution"] == "manual_candidate"
    assert candidate.json()["canonical_configuration_id"] is None


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
        assert _error(timeout)["code"] == "VIN_PROVIDER_TIMEOUT"
        assert VALID_VIN not in timeout.text

        oversized = client.post(
            "/api/v1/user-vehicles/manual",
            content="x" * (33 * 1024),
            headers={"Content-Type": "application/json", **CSRF},
        )
        assert oversized.status_code == 413
        assert _error(oversized)["code"] == "REQUEST_PAYLOAD_TOO_LARGE"

    async def unsupported_decoder(_: str) -> ProviderIdentity:
        return ProviderIdentity(
            year=2003,
            make="Audi",
            model="A4",
            trim=None,
            body_style="Sedan",
            engine=None,
            transmission=None,
            drivetrain=None,
        )

    monkeypatch.setattr(user_vehicle_service, "decode_vin_values_extended", unsupported_decoder)
    with TestClient(app) as client:
        _register(client, "unsupported")
        unsupported = client.post(
            "/api/v1/user-vehicles/vin/decode",
            json={"market": "US", "vin": VALID_VIN},
            headers=CSRF,
        )
    assert unsupported.status_code == 422
    assert _error(unsupported)["code"] == "VIN_UNSUPPORTED_VEHICLE"


def test_private_vehicle_routes_require_auth_and_csrf() -> None:
    with TestClient(app) as client:
        unauthenticated = client.get("/api/v1/user-vehicles")
        assert unauthenticated.status_code == 401
        assert _error(unauthenticated)["code"] == "AUTH_REQUIRED"

        _register(client, "csrf_vehicle")
        missing_csrf = client.post(
            "/api/v1/user-vehicles/manual",
            json={
                "selection": {
                    "year": 2003,
                    "market": "US",
                    "make": "Honda",
                    "model": "Accord",
                }
            },
        )
        assert missing_csrf.status_code == 403
        assert _error(missing_csrf)["code"] == "AUTH_CSRF_FAILED"
