from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import ErrorCode, PartGraphError
from .models import ProviderConnection
from .schemas import ProviderCreate, ProviderRead, ProviderUpdate


def serialize_provider(provider: ProviderConnection) -> ProviderRead:
    return ProviderRead(
        id=provider.id,
        provider_key=provider.provider_key,
        display_name=provider.display_name,
        provider_kind=provider.provider_kind,
        base_url=provider.base_url,
        enabled=provider.enabled,
        capabilities=list(provider.capabilities or []),
        secret_configured=provider.secret_ref is not None,
        notes=provider.notes,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


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

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(provider, field, value)
    provider.updated_by = actor_id
    provider.updated_at = datetime.now(UTC)
    await session.flush()
    return serialize_provider(provider)
