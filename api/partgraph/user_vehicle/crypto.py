import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import settings

NONCE_BYTES = 12
KEY_BYTES = 32


class VinCryptoError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProtectedVin:
    ciphertext: bytes
    nonce: bytes
    key_version: int
    fingerprint: str


def _decode_key(value: str) -> bytes:
    try:
        key = base64.b64decode(value.encode("ascii"), altchars=b"-_", validate=True)
    except (ValueError, UnicodeEncodeError) as exc:
        raise VinCryptoError("VIN protection key configuration is invalid.") from exc
    if len(key) != KEY_BYTES:
        raise VinCryptoError("VIN protection key configuration is invalid.")
    return key


def _encryption_keyring() -> dict[int, bytes]:
    raw = settings.vin_encryption_keys
    if not raw:
        raise VinCryptoError("VIN protection is not configured.")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise VinCryptoError("VIN protection key configuration is invalid.") from exc
    if not isinstance(payload, dict) or not payload:
        raise VinCryptoError("VIN protection key configuration is invalid.")

    keys: dict[int, bytes] = {}
    try:
        for version, value in payload.items():
            numeric_version = int(version)
            if numeric_version < 1 or not isinstance(value, str):
                raise ValueError
            keys[numeric_version] = _decode_key(value)
    except (TypeError, ValueError) as exc:
        raise VinCryptoError("VIN protection key configuration is invalid.") from exc

    if settings.vin_active_key_version not in keys:
        raise VinCryptoError("VIN active key version is not configured.")
    return keys


def _lookup_key() -> bytes:
    raw = settings.vin_lookup_key
    if not raw:
        raise VinCryptoError("VIN lookup protection is not configured.")
    return _decode_key(raw)


def vin_fingerprint(vin: str, *, user_id: UUID) -> str:
    scoped_value = f"{user_id}\x1f{vin}".encode("ascii")
    return hmac.new(_lookup_key(), scoped_value, hashlib.sha256).hexdigest()


def _aad(version: int, user_id: UUID) -> bytes:
    return f"partgraph:user-vehicle:vin:v{version}:owner:{user_id}".encode("ascii")


def protect_vin(vin: str, *, user_id: UUID) -> ProtectedVin:
    keys = _encryption_keyring()
    version = settings.vin_active_key_version
    nonce = secrets.token_bytes(NONCE_BYTES)
    ciphertext = AESGCM(keys[version]).encrypt(
        nonce,
        vin.encode("ascii"),
        _aad(version, user_id),
    )
    return ProtectedVin(
        ciphertext=ciphertext,
        nonce=nonce,
        key_version=version,
        fingerprint=vin_fingerprint(vin, user_id=user_id),
    )


def reveal_vin(
    *,
    ciphertext: bytes,
    nonce: bytes,
    key_version: int,
    user_id: UUID,
) -> str:
    keys = _encryption_keyring()
    key = keys.get(key_version)
    if key is None:
        raise VinCryptoError("VIN key version is unavailable.")
    try:
        plaintext = AESGCM(key).decrypt(
            nonce,
            ciphertext,
            _aad(key_version, user_id),
        )
        return plaintext.decode("ascii")
    except (InvalidTag, ValueError, UnicodeDecodeError) as exc:
        raise VinCryptoError("VIN ciphertext authentication failed.") from exc
