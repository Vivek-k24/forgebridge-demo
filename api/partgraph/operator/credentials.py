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


class ProviderCredentialError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProtectedProviderCredential:
    ciphertext: bytes
    nonce: bytes
    key_version: int
    fingerprint: str
    hint: str


def _decode_key(value: str) -> bytes:
    try:
        key = base64.b64decode(value.encode("ascii"), altchars=b"-_", validate=True)
    except (ValueError, UnicodeEncodeError) as exc:
        raise ProviderCredentialError("Provider credential key configuration is invalid.") from exc
    if len(key) != KEY_BYTES:
        raise ProviderCredentialError("Provider credential key configuration is invalid.")
    return key


def _keyring() -> dict[int, bytes]:
    raw = settings.provider_credential_keys
    if not raw:
        raise ProviderCredentialError("Provider credential encryption is not configured.")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderCredentialError("Provider credential key configuration is invalid.") from exc
    if not isinstance(payload, dict) or not payload:
        raise ProviderCredentialError("Provider credential key configuration is invalid.")

    keys: dict[int, bytes] = {}
    try:
        for version, value in payload.items():
            numeric_version = int(version)
            if numeric_version < 1 or not isinstance(value, str):
                raise ValueError
            keys[numeric_version] = _decode_key(value)
    except (TypeError, ValueError) as exc:
        raise ProviderCredentialError("Provider credential key configuration is invalid.") from exc

    if settings.provider_credential_active_key_version not in keys:
        raise ProviderCredentialError("Provider credential active key version is not configured.")
    return keys


def _aad(version: int, provider_id: UUID) -> bytes:
    return f"partgraph:provider-credential:v{version}:provider:{provider_id}".encode("ascii")


def _fingerprint(value: str, key: bytes) -> str:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


def _hint(value: str) -> str:
    return value[-4:] if len(value) >= 4 else value


def protect_provider_credential(
    value: str,
    *,
    provider_id: UUID,
) -> ProtectedProviderCredential:
    keys = _keyring()
    version = settings.provider_credential_active_key_version
    key = keys[version]
    nonce = secrets.token_bytes(NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(
        nonce,
        value.encode("utf-8"),
        _aad(version, provider_id),
    )
    return ProtectedProviderCredential(
        ciphertext=ciphertext,
        nonce=nonce,
        key_version=version,
        fingerprint=_fingerprint(value, key),
        hint=_hint(value),
    )


def reveal_provider_credential(
    *,
    ciphertext: bytes,
    nonce: bytes,
    key_version: int,
    provider_id: UUID,
) -> str:
    keys = _keyring()
    key = keys.get(key_version)
    if key is None:
        raise ProviderCredentialError("Provider credential key version is unavailable.")
    try:
        plaintext = AESGCM(key).decrypt(
            nonce,
            ciphertext,
            _aad(key_version, provider_id),
        )
        return plaintext.decode("utf-8")
    except (InvalidTag, ValueError, UnicodeDecodeError) as exc:
        raise ProviderCredentialError("Provider credential ciphertext authentication failed.") from exc
