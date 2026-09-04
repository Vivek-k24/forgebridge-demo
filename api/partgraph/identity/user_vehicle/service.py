from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..errors import ErrorCode, PartGraphError
from ..vehicle.models import VehicleConfiguration
from ..vehicle.policy import validate_supported_year
from ..vehicle.schemas import VehicleConfigurationRead
from ..vehicle.service import resolve_selection
from ..vehicle.taxonomy import (
    VehicleIdentityError,
    canonical_market,
    canonicalize_fields,
    comparison_key,
)
from .crypto import VinCryptoError, protect_vin, vin_fingerprint
from .models import UserVehicle, VinDecodeCache
from .schemas import (
    ManualUserVehicleCreate,
    VehicleIdentitySnapshot,
    VinDecodeRead,
    VinUserVehicleCreate,
)
from .vin import ProviderIdentity, decode_vin_values_extended, mask_vin, validate_vin

Resolution = Literal["matched", "ambiguous", "manual_candidate"]
VinSource = Literal["provider", "cache"]
OPTIONAL_MATCH_FIELDS = (
    "generation",
    "trim",
    "body_style",
    "engine",
    "transmission",
    "drivetrain",
)
STRUCTURED_FIELDS = {"engine", "transmission"}


@dataclass(frozen=True, slots=True)
class ResolvedVin:
    source: VinSource
    provider: str
    masked_vin: str
    observed_at: datetime
    expires_at: datetime
    resolution: Resolution
    identity: VehicleIdentitySnapshot
    matches: list[VehicleConfiguration]


def _crypto_error(_: VinCryptoError) -> PartGraphError:
    return PartGraphError(
        code=ErrorCode.VIN_CRYPTO_UNAVAILABLE,
        message="VIN protection is unavailable. Use vehicle details or try again later.",
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        retryable=False,
    )


def _snapshot_from_configuration(configuration: VehicleConfiguration) -> VehicleIdentitySnapshot:
    return VehicleIdentitySnapshot(
        year=configuration.year,
        market=configuration.market,
        make=configuration.make,
        model=configuration.model,
        generation=configuration.generation,
        trim=configuration.trim,
        body_style=configuration.body_style,
        engine=configuration.engine,
        transmission=configuration.transmission,
        drivetrain=configuration.drivetrain,
    )


def _detail_tokens(field: str, value: str) -> set[str]:
    return {token for token in comparison_key(field, value).split("|") if token}


def _details_compatible(field: str, candidate: str | None, observed: str | None) -> bool:
    if candidate is None or observed is None:
        return True
    if field in STRUCTURED_FIELDS:
        candidate_tokens = _detail_tokens(field, candidate)
        observed_tokens = _detail_tokens(field, observed)
        return candidate_tokens <= observed_tokens or observed_tokens <= candidate_tokens
    return comparison_key(field, candidate) == comparison_key(field, observed)


async def _resolve_identity_snapshot(
    session: AsyncSession,
    identity: VehicleIdentitySnapshot,
) -> tuple[Resolution, list[VehicleConfiguration]]:
    rows = list(
        await session.scalars(
            select(VehicleConfiguration).where(
                VehicleConfiguration.year == identity.year,
                VehicleConfiguration.market == identity.market,
                VehicleConfiguration.make == identity.make,
            )
        )
    )
    model_key = comparison_key("model", identity.model)
    matches = [row for row in rows if comparison_key("model", row.model) == model_key]

    for field in OPTIONAL_MATCH_FIELDS:
        observed = getattr(identity, field)
        if observed is None:
            continue
        matches = [
            row
            for row in matches
            if _details_compatible(field, getattr(row, field), observed)
        ]

    if not matches:
        return "manual_candidate", []
    if len(matches) == 1:
        return "matched", matches
    return "ambiguous", matches[:10]


def _provider_snapshot(provider: ProviderIdentity, market: str) -> VehicleIdentitySnapshot:
    try:
        year = validate_supported_year(provider.year)
        normalized = canonicalize_fields(
            year=year,
            market=market,
            make=provider.make,
            model=provider.model,
            generation=None,
            trim=provider.trim,
            body_style=provider.body_style,
            engine=provider.engine,
            transmission=provider.transmission,
            drivetrain=provider.drivetrain,
        )
    except (ValueError, VehicleIdentityError) as exc:
        raise PartGraphError(
            code=ErrorCode.VIN_UNSUPPORTED_VEHICLE,
            message="VIN decoded to a vehicle outside the current PartGraph scope.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        ) from exc

    return VehicleIdentitySnapshot.model_validate(normalized)


async def _cache_observation(
    session: AsyncSession,
    *,
    user_id: UUID,
    fingerprint: str,
    market: str,
    identity: VehicleIdentitySnapshot,
    resolution: Resolution,
    matches: list[VehicleConfiguration],
    observed_at: datetime,
    expires_at: datetime,
) -> None:
    match_ids = [str(item.id) for item in matches]
    statement = (
        insert(VinDecodeCache)
        .values(
            user_id=user_id,
            vin_fingerprint=fingerprint,
            market=market,
            identity_resolution=resolution,
            identity_snapshot=identity.model_dump(mode="json"),
            canonical_match_ids=match_ids,
            provider="nhtsa_vpic",
            observed_at=observed_at,
            expires_at=expires_at,
        )
        .on_conflict_do_update(
            constraint="uq_vin_decode_cache_owner_vin_market",
            set_={
                "identity_resolution": resolution,
                "identity_snapshot": identity.model_dump(mode="json"),
                "canonical_match_ids": match_ids,
                "provider": "nhtsa_vpic",
                "observed_at": observed_at,
                "expires_at": expires_at,
                "updated_at": datetime.now(UTC),
            },
        )
    )
    await session.execute(statement)


async def _decode_validated_vin(
    session: AsyncSession,
    *,
    user_id: UUID,
    vin: str,
    fingerprint: str,
    market: str,
) -> ResolvedVin:
    now = datetime.now(UTC)
    cached = await session.scalar(
        select(VinDecodeCache).where(
            VinDecodeCache.user_id == user_id,
            VinDecodeCache.vin_fingerprint == fingerprint,
            VinDecodeCache.market == market,
            VinDecodeCache.expires_at > now,
        )
    )
    if cached is not None:
        try:
            identity = VehicleIdentitySnapshot.model_validate(cached.identity_snapshot)
        except ValidationError:
            pass
        else:
            resolution, matches = await _resolve_identity_snapshot(session, identity)
            match_ids = [str(item.id) for item in matches]
            if resolution != cached.identity_resolution or match_ids != cached.canonical_match_ids:
                cached.identity_resolution = resolution
                cached.canonical_match_ids = match_ids
                cached.updated_at = now
            return ResolvedVin(
                source="cache",
                provider=cached.provider,
                masked_vin=mask_vin(vin),
                observed_at=cached.observed_at,
                expires_at=cached.expires_at,
                resolution=resolution,
                identity=identity,
                matches=matches,
            )

    provider = await decode_vin_values_extended(vin)
    identity = _provider_snapshot(provider, market)
    resolution, matches = await _resolve_identity_snapshot(session, identity)
    observed_at = datetime.now(UTC)
    expires_at = observed_at + timedelta(hours=settings.vin_cache_hours)
    await _cache_observation(
        session,
        user_id=user_id,
        fingerprint=fingerprint,
        market=market,
        identity=identity,
        resolution=resolution,
        matches=matches,
        observed_at=observed_at,
        expires_at=expires_at,
    )
    return ResolvedVin(
        source="provider",
        provider="nhtsa_vpic",
        masked_vin=mask_vin(vin),
        observed_at=observed_at,
        expires_at=expires_at,
        resolution=resolution,
        identity=identity,
        matches=matches,
    )


async def decode_user_vin(
    session: AsyncSession,
    *,
    user_id: UUID,
    market: str,
    vin_value: str,
) -> ResolvedVin:
    vin = validate_vin(vin_value)
    try:
        fingerprint = vin_fingerprint(vin, user_id=user_id)
    except VinCryptoError as exc:
        raise _crypto_error(exc) from exc

    try:
        normalized_market = canonical_market(market)
    except VehicleIdentityError as exc:
        raise PartGraphError(
            code=ErrorCode.REQUEST_VALIDATION_FAILED,
            message=str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        ) from exc

    return await _decode_validated_vin(
        session,
        user_id=user_id,
        vin=vin,
        fingerprint=fingerprint,
        market=normalized_market,
    )


async def create_manual_user_vehicle(
    session: AsyncSession,
    *,
    user_id: UUID,
    payload: ManualUserVehicleCreate,
) -> UserVehicle:
    try:
        resolution, _, matches = await resolve_selection(session, payload.selection)
    except VehicleIdentityError as exc:
        raise PartGraphError(
            code=ErrorCode.REQUEST_VALIDATION_FAILED,
            message=str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        ) from exc

    if resolution != "matched" or len(matches) != 1:
        message = (
            "This vehicle selection matches multiple canonical configurations. "
            "Choose a more exact configuration before saving."
            if resolution == "ambiguous"
            else "This vehicle selection is not verified in PartGraph canonical vehicle data "
            "and cannot be saved yet."
        )
        raise PartGraphError(
            code=ErrorCode.USER_VEHICLE_IDENTITY_UNVERIFIED,
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details={"resolution": resolution},
        )

    configuration = matches[0]
    identity = _snapshot_from_configuration(configuration)
    vehicle = UserVehicle(
        user_id=user_id,
        canonical_configuration_id=configuration.id,
        nickname=payload.nickname,
        identity_source="manual",
        identity_resolution="matched",
        identity_snapshot=identity.model_dump(mode="json"),
    )
    session.add(vehicle)
    await session.flush()
    return vehicle


async def create_vin_user_vehicle(
    session: AsyncSession,
    *,
    user_id: UUID,
    payload: VinUserVehicleCreate,
) -> UserVehicle:
    vin = validate_vin(payload.vin)
    try:
        protected = protect_vin(vin, user_id=user_id)
    except VinCryptoError as exc:
        raise _crypto_error(exc) from exc

    existing = await session.scalar(
        select(UserVehicle.id).where(
            UserVehicle.user_id == user_id,
            UserVehicle.vin_fingerprint == protected.fingerprint,
        )
    )
    if existing is not None:
        raise PartGraphError(
            code=ErrorCode.USER_VEHICLE_VIN_EXISTS,
            message="This VIN is already saved in your PartGraph account.",
            status_code=status.HTTP_409_CONFLICT,
        )

    try:
        market = canonical_market(payload.market)
    except VehicleIdentityError as exc:
        raise PartGraphError(
            code=ErrorCode.REQUEST_VALIDATION_FAILED,
            message=str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        ) from exc

    resolved = await _decode_validated_vin(
        session,
        user_id=user_id,
        vin=vin,
        fingerprint=protected.fingerprint,
        market=market,
    )
    canonical_configuration_id = (
        resolved.matches[0].id if resolved.resolution == "matched" else None
    )

    statement = (
        insert(UserVehicle)
        .values(
            user_id=user_id,
            canonical_configuration_id=canonical_configuration_id,
            nickname=payload.nickname,
            identity_source="vin",
            identity_resolution=resolved.resolution,
            identity_snapshot=resolved.identity.model_dump(mode="json"),
            vin_ciphertext=protected.ciphertext,
            vin_nonce=protected.nonce,
            vin_key_version=protected.key_version,
            vin_fingerprint=protected.fingerprint,
            vin_last6=vin[-6:],
            decoder_provider=resolved.provider,
            decoder_observed_at=resolved.observed_at,
        )
        .on_conflict_do_nothing(constraint="uq_user_vehicles_owner_vin")
        .returning(UserVehicle.id)
    )
    created_id = (await session.execute(statement)).scalar_one_or_none()
    if created_id is None:
        raise PartGraphError(
            code=ErrorCode.USER_VEHICLE_VIN_EXISTS,
            message="This VIN is already saved in your PartGraph account.",
            status_code=status.HTTP_409_CONFLICT,
        )

    vehicle = await session.get(UserVehicle, created_id)
    if vehicle is None:
        raise RuntimeError("created user vehicle disappeared after insert")
    return vehicle


async def list_user_vehicles(
    session: AsyncSession,
    *,
    user_id: UUID,
    include_archived: bool,
    limit: int,
) -> list[UserVehicle]:
    statement = select(UserVehicle).where(UserVehicle.user_id == user_id)
    if not include_archived:
        statement = statement.where(UserVehicle.archived_at.is_(None))
    rows = await session.scalars(
        statement.order_by(UserVehicle.updated_at.desc()).limit(limit)
    )
    return list(rows)


async def get_user_vehicle(
    session: AsyncSession,
    *,
    user_id: UUID,
    vehicle_id: UUID,
) -> UserVehicle | None:
    return await session.scalar(
        select(UserVehicle).where(
            UserVehicle.id == vehicle_id,
            UserVehicle.user_id == user_id,
        )
    )


async def archive_user_vehicle(
    session: AsyncSession,
    *,
    user_id: UUID,
    vehicle_id: UUID,
) -> UserVehicle:
    vehicle = await get_user_vehicle(session, user_id=user_id, vehicle_id=vehicle_id)
    if vehicle is None:
        raise PartGraphError(
            code=ErrorCode.USER_VEHICLE_NOT_FOUND,
            message="Vehicle not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if vehicle.archived_at is None:
        now = datetime.now(UTC)
        vehicle.archived_at = now
        vehicle.updated_at = now
        await session.flush()
    return vehicle


def serialize_user_vehicle(vehicle: UserVehicle) -> dict[str, object]:
    identity = VehicleIdentitySnapshot.model_validate(vehicle.identity_snapshot)
    return {
        "id": vehicle.id,
        "nickname": vehicle.nickname,
        "canonical_configuration_id": vehicle.canonical_configuration_id,
        "identity_source": vehicle.identity_source,
        "identity_resolution": vehicle.identity_resolution,
        "identity": identity,
        "masked_vin": f"***********{vehicle.vin_last6}" if vehicle.vin_last6 else None,
        "decoder_provider": vehicle.decoder_provider,
        "decoder_observed_at": vehicle.decoder_observed_at,
        "archived_at": vehicle.archived_at,
        "created_at": vehicle.created_at,
        "updated_at": vehicle.updated_at,
    }


def serialize_vin_resolution(resolved: ResolvedVin) -> VinDecodeRead:
    return VinDecodeRead(
        source=resolved.source,
        provider=resolved.provider,
        masked_vin=resolved.masked_vin,
        observed_at=resolved.observed_at,
        expires_at=resolved.expires_at,
        resolution=resolved.resolution,
        identity=resolved.identity,
        matches=[VehicleConfigurationRead.model_validate(item) for item in resolved.matches],
    )
