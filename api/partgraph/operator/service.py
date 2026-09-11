from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import ErrorCode, PartGraphError
from .credentials import ProviderCredentialError, protect_provider_credential
from .models import ProviderConnection
from .schemas import ProviderCreate, ProviderRead, ProviderUpdate


def _credential_storage(provider: ProviderConnection) -> str | None:
    if provider.credential_ciphertext is not None:
        return "encrypted_database"
    if provider.secret_ref is not None:
        return "external_reference"
    return None


def serialize_provider(provider: ProviderConnection) -> ProviderRead:
    storage = _credential_storage(provider)
    return ProviderRead(
        id=provider.id,
        provider_key=provider.provider_key,
        display_name=provider.display_name,
        provider_kind=provider.provider_kind,
        base_url=provider.base_url,
        enabled=provider.enabled,
        capabilities=list(provider.capabilities or []),
        secret_configured=storage is not None,
        secret_storage=storage,
        secret_hint=(provider.credential_hint if storage == "encrypted_database" else None),
        notes=provider.notes,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


def _clear_encrypted_credential(provider: ProviderConnection) -> None:
    provider.credential_ciphertext = None
    provider.credential_nonce = None
    provider.credential_key_version = None
    provider.credential_fingerprint = None
    provider.credential_hint = None


def _set_encrypted_credential(provider: ProviderConnection, value: str) -> None:
    try:
        protected = protect_provider_credential(value, provider_id=provider.id)
    except ProviderCredentialError as exc:
        raise PartGraphError(
            code="PROVIDER_CREDENTIAL_CRYPTO_UNAVAILABLE",
            message="Provider credential encryption is not configured or is invalid.",
            status_code=503,
            retryable=False,
        ) from exc
    provider.credential_ciphertext = protected.ciphertext
    provider.credential_nonce = protected.nonce
    provider.credential_key_version = protected.key_version
    provider.credential_fingerprint = protected.fingerprint
    provider.credential_hint = protected.hint
    provider.secret_ref = None


async def list_providers(session: AsyncSession) -> list[ProviderRead]:
    rows = list(
        await session.scalars(
            select(ProviderConnection).order_by(
                ProviderConnection.provider_kind,
                ProviderConnection.display_name,
            )
        )
    )
    return [serialize_provider(row) for row in rows]


async def create_provider(
    session: AsyncSession,
    *,
    actor_id: UUID,
    payload: ProviderCreate,
) -> ProviderRead:
    provider = ProviderConnection(
        id=uuid4(),
        provider_key=payload.provider_key,
        display_name=payload.display_name,
        provider_kind=payload.provider_kind,
        base_url=payload.base_url,
        enabled=payload.enabled,
        capabilities=payload.capabilities,
        secret_ref=payload.secret_ref,
        notes=payload.notes,
        created_by=actor_id,
        updated_by=actor_id,
    )
    if payload.credential is not None:
        _set_encrypted_credential(provider, payload.credential.get_secret_value())
    session.add(provider)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise PartGraphError(
            code=ErrorCode.REQUEST_CONFLICT,
            message="A provider with this key already exists.",
            status_code=409,
        ) from exc
    return serialize_provider(provider)


async def update_provider(
    session: AsyncSession,
    *,
    actor_id: UUID,
    provider_id: UUID,
    payload: ProviderUpdate,
) -> ProviderRead:
    provider = await session.get(ProviderConnection, provider_id)
    if provider is None:
        raise PartGraphError(
            code=ErrorCode.REQUEST_NOT_FOUND,
            message="Provider connection not found.",
            status_code=404,
        )

    changes = payload.model_dump(
        exclude_unset=True,
        exclude={"credential", "clear_credential", "secret_ref"},
    )
    for field, value in changes.items():
        setattr(provider, field, value)

    if payload.clear_credential:
        _clear_encrypted_credential(provider)
        provider.secret_ref = None
    elif payload.credential is not None:
        _set_encrypted_credential(provider, payload.credential.get_secret_value())
    elif "secret_ref" in payload.model_fields_set:
        provider.secret_ref = payload.secret_ref
        if payload.secret_ref is not None:
            _clear_encrypted_credential(provider)

    provider.updated_by = actor_id
    provider.updated_at = datetime.now(UTC)
    await session.flush()
    return serialize_provider(provider)
