from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import partgraph.identity.user_vehicle.crypto as vin_crypto
import partgraph.identity.user_vehicle.vin_decode as vin_decode
from partgraph.identity.user_vehicle.vin import ProviderIdentity
from partgraph.main import app

CSRF = {"X-PartGraph-CSRF": "1"}
PASSWORD = "correct-horse-battery-staple"
VALID_VIN = "1HGCM82633A004352"


def _register(client: TestClient) -> None:
    suffix = uuid4().hex[:12]
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"vin-fallback-{suffix}@example.com",
            "username": f"vin_fallback_{suffix}"[:32],
            "password": PASSWORD,
        },
        headers=CSRF,
    )
    assert response.status_code == 200, response.text


def test_decode_and_identity_save_work_without_storage_keys_while_vin_storage_stays_protected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        vin_crypto,
        "settings",
        SimpleNamespace(
            vin_encryption_keys=None,
            vin_active_key_version=1,
            vin_lookup_key=None,
        ),
    )

    calls = 0

    async def fake_decoder(_: str) -> ProviderIdentity:
        nonlocal calls
        calls += 1
        return ProviderIdentity(
            year=2003,
            make="Honda",
            model="Accord",
            trim="EX",
            body_style="Sedan",
            engine="3.0L V6",
            transmission="5-speed Automatic",
            drivetrain="FWD",
        )

    monkeypatch.setattr(vin_decode, "decode_vin_values_extended", fake_decoder)

    with TestClient(app) as client:
        _register(client)
        decoded = client.post(
            "/api/v1/user-vehicles/vin/decode",
            json={"market": "US", "vin": VALID_VIN},
            headers=CSRF,
        )
        protected_save = client.post(
            "/api/v1/user-vehicles/vin",
            json={"market": "US", "vin": VALID_VIN},
            headers=CSRF,
        )
        identity_save = client.post(
            "/api/v1/user-vehicles/vin/identity",
            json={"market": "US", "vin": VALID_VIN, "nickname": "Accord"},
            headers=CSRF,
        )

    assert decoded.status_code == 200, decoded.text
    assert decoded.json()["source"] == "provider"
    assert decoded.json()["provider"] == "nhtsa_vpic"
    assert decoded.json()["masked_vin"] == "***********004352"
    assert VALID_VIN not in decoded.text

    assert protected_save.status_code == 503, protected_save.text
    error = protected_save.json()["error"]
    assert error["code"] == "VIN_CRYPTO_UNAVAILABLE"
    assert VALID_VIN not in protected_save.text

    assert identity_save.status_code == 201, identity_save.text
    saved = identity_save.json()
    assert saved["nickname"] == "Accord"
    assert saved["identity_source"] == "vin"
    assert saved["identity"]["year"] == 2003
    assert saved["identity"]["make"] == "Honda"
    assert saved["identity"]["model"] == "Accord"
    assert saved["identity"]["trim"] == "EX"
    assert saved["masked_vin"] is None
    assert saved["decoder_provider"] == "nhtsa_vpic"
    assert VALID_VIN not in identity_save.text
    assert calls == 2
