from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .models import VehicleConfiguration
from .schemas import VehicleConfigurationInput


def _canonical(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.casefold().split())


def identity_hash(payload: VehicleConfigurationInput) -> str:
    parts = (
        str(payload.year),
        _canonical(payload.market),
        _canonical(payload.make),
        _canonical(payload.model),
        _canonical(payload.generation),
        _canonical(payload.trim),
        _canonical(payload.body_style),
        _canonical(payload.engine),
        _canonical(payload.transmission),
        _canonical(payload.drivetrain),
    )
    return sha256("\x1f".join(parts).encode()).hexdigest()


async def create_or_get_configuration(
    session: AsyncSession,
    payload: VehicleConfigurationInput,
) -> tuple[VehicleConfiguration, bool]:
    fingerprint = identity_hash(payload)
    existing = await session.scalar(
        select(VehicleConfiguration).where(VehicleConfiguration.identity_hash == fingerprint)
    )
    if existing is not None:
        return existing, False

    configuration = VehicleConfiguration(
        identity_hash=fingerprint,
        **payload.model_dump(),
        identity_source="manual",
        verification_status="unverified",
    )
    session.add(configuration)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(
            select(VehicleConfiguration).where(VehicleConfiguration.identity_hash == fingerprint)
        )
        if existing is None:
            raise
        return existing, False

    await session.refresh(configuration)
    return configuration, True


async def get_configuration(
    session: AsyncSession,
    configuration_id: UUID,
) -> VehicleConfiguration | None:
    return await session.get(VehicleConfiguration, configuration_id)


async def list_configurations(
    session: AsyncSession,
    limit: int,
) -> list[VehicleConfiguration]:
    rows = await session.scalars(
        select(VehicleConfiguration)
        .order_by(VehicleConfiguration.created_at.desc())
        .limit(limit)
    )
    return list(rows)
