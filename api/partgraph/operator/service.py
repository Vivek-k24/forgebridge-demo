import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import ErrorCode, PartGraphError
from ..identity.auth.models import User
from .credentials import ProviderCredentialError, protect_provider_credential
from .models import OperatorAuditEvent, ProviderConnection
from .schemas import (
    OperatorAuditRead,
    PreviewOperatorBootstrapStatus,
    ProviderCreate,
    ProviderRead,
    ProviderUpdate,
)

_PREVIEW_BOOTSTRAP_BRANCH = "partgraph-mvp-consolidation"
_PREVIEW_BOOTSTRAP_LOCK = 731_947_211


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


def serialize_audit_event(event: OperatorAuditEvent) -> OperatorAuditRead:
    return OperatorAuditRead(
        id=event.id,
        actor_user_id=event.actor_user_id,
        action=event.action,
        target_type=event.target_type,
        target_id=event.target_id,
        event_data=dict(event.event_data or {}),
        created_at=event.created_at,
    )


def _record_audit_event(
    session: AsyncSession,
    *,
    actor_id: UUID,
    action: str,
    target_type: str,
    target_id: UUID,
    event_data: dict[str, object] | None = None,
) -> None:
    session.add(
        OperatorAuditEvent(
            actor_user_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            event_data=event_data or {},
        )
    )


def _record_provider_audit(
    session: AsyncSession,
    *,
    actor_id: UUID,
    action: str,
    provider: ProviderConnection,
    event_data: dict[str, object] | None = None,
) -> None:
    _record_audit_event(
        session,
        actor_id=actor_id,
        action=action,
        target_type="provider",
        target_id=provider.id,
        event_data=event_data,
    )


def _preview_bootstrap_environment() -> bool:
    return (
        os.getenv("VERCEL") == "1"
        and os.getenv("VERCEL_ENV") == "preview"
        and os.getenv("VERCEL_GIT_COMMIT_REF") == _PREVIEW_BOOTSTRAP_BRANCH
    )


async def preview_operator_bootstrap_status(
    session: AsyncSession,
) -> PreviewOperatorBootstrapStatus:
    if not _preview_bootstrap_environment():
        return PreviewOperatorBootstrapStatus(available=False)
    operator_id = await session.scalar(
        select(User.id).where(User.role == "operator_admin").limit(1)
    )
    return PreviewOperatorBootstrapStatus(available=operator_id is None)


async def bootstrap_preview_operator(
    session: AsyncSession,
    *,
    user: User,
) -> None:
    if not _preview_bootstrap_environment():
        raise PartGraphError(
            code=ErrorCode.REQUEST_NOT_FOUND,
            message="Preview operator bootstrap is unavailable.",
            status_code=404,
        )

    await session.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": _PREVIEW_BOOTSTRAP_LOCK})
    if user.role == "operator_admin":
        return

    operator_id = await session.scalar(
        select(User.id).where(User.role == "operator_admin").limit(1)
    )
    if operator_id is not None:
        raise PartGraphError(
            code=ErrorCode.REQUEST_CONFLICT,
            message="A preview operator has already been established.",
            status_code=409,
        )

    user.role = "operator_admin"
    _record_audit_event(
        session,
        actor_id=user.id,
        action="preview_operator_bootstrap",
        target_type="user",
        target_id=user.id,
        event_data={"environment": "preview", "branch": _PREVIEW_BOOTSTRAP_BRANCH},
    )
    await session.flush()


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


async def list_operator_audit(session: AsyncSession, *, limit: int = 50) -> list[OperatorAuditRead]:
    rows = list(
        await session.scalars(
            select(OperatorAuditEvent)
            .order_by(OperatorAuditEvent.created_at.desc(), OperatorAuditEvent.id.desc())
            .limit(limit)
        )
    )
    return [serialize_audit_event(row) for row in rows]


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

    _record_provider_audit(
        session,
        actor_id=actor_id,
        action="provider_created",
        provider=provider,
        event_data={
            "provider_key": provider.provider_key,
            "provider_kind": provider.provider_kind,
            "enabled": provider.enabled,
            "credential_storage": _credential_storage(provider),
        },
    )
    await session.flush()
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

    previous_enabled = provider.enabled
    previous_storage = _credential_storage(provider)
    changes = payload.model_dump(
        exclude_unset=True,
        exclude={"credential", "clear_credential", "secret_ref"},
    )
    for field, value in changes.items():
        setattr(provider, field, value)

    credential_changed = False
    if payload.clear_credential:
        _clear_encrypted_credential(provider)
        provider.secret_ref = None
        credential_changed = previous_storage is not None
    elif payload.credential is not None:
        _set_encrypted_credential(provider, payload.credential.get_secret_value())
        credential_changed = True
    elif "secret_ref" in payload.model_fields_set:
        provider.secret_ref = payload.secret_ref
        if payload.secret_ref is not None:
            _clear_encrypted_credential(provider)
        credential_changed = previous_storage != _credential_storage(provider)

    provider.updated_by = actor_id
    provider.updated_at = datetime.now(UTC)
    await session.flush()

    non_state_fields = sorted(field for field in changes if field != "enabled")
    if non_state_fields:
        _record_provider_audit(
            session,
            actor_id=actor_id,
            action="provider_updated",
            provider=provider,
            event_data={
                "provider_key": provider.provider_key,
                "changed_fields": non_state_fields,
            },
        )
    if "enabled" in changes and provider.enabled != previous_enabled:
        _record_provider_audit(
            session,
            actor_id=actor_id,
            action="provider_enabled" if provider.enabled else "provider_disabled",
            provider=provider,
            event_data={"provider_key": provider.provider_key},
        )
    if credential_changed:
        storage = _credential_storage(provider)
        _record_provider_audit(
            session,
            actor_id=actor_id,
            action="provider_credential_saved" if storage is not None else "provider_credential_removed",
            provider=provider,
            event_data={
                "provider_key": provider.provider_key,
                "credential_storage": storage,
            },
        )

    await session.flush()
    return serialize_provider(provider)
