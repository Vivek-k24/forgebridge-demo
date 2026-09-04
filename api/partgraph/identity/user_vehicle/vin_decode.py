from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import ErrorCode, PartGraphError
from ..vehicle.taxonomy import VehicleIdentityError, canonical_market
from .crypto import VinCryptoError, vin_fingerprint
from .models import UserVehicle
from .schemas import VinUserVehicleCreate
from .service import (
    ResolvedVin,
    _decode_validated_vin,
    _provider_snapshot,
    _resolve_identity_snapshot,
)
from .vin import decode_vin_values_extended, mask_vin, validate_vin


async def _decode_provider_without_persistence(
    session: AsyncSession,
    *,
    vin: str,
    market: str,
) -> ResolvedVin:
    provider = await decode_vin_values_extended(vin)
    identity = _provider_snapshot(provider, market)
    resolution, matches = await _resolve_identity_snapshot(session, identity)
    observed_at = datetime.now(UTC)
    return ResolvedVin(
        source="provider",
        provider="nhtsa_vpic",
        masked_vin=mask_vin(vin),
        observed_at=observed_at,
        expires_at=observed_at,
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
    """Decode a VIN without making protected storage keys a lookup prerequisite.

    When the per-owner lookup key is available, the normal privacy-preserving cache
    path is used. Hosted runtimes without VIN storage keys still may perform a
    decode-only NHTSA vPIC lookup; the raw VIN and provider response are not
    persisted in that fallback path. Saving the protected VIN continues to use
    protect_vin() and therefore still requires the configured encryption keyring
    and lookup key.
    """

    vin = validate_vin(vin_value)
    try:
        normalized_market = canonical_market(market)
    except VehicleIdentityError as exc:
        raise PartGraphError(
            code=ErrorCode.REQUEST_VALIDATION_FAILED,
            message=str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        ) from exc

    try:
        fingerprint = vin_fingerprint(vin, user_id=user_id)
    except VinCryptoError:
        return await _decode_provider_without_persistence(
            session,
            vin=vin,
            market=normalized_market,
        )

    return await _decode_validated_vin(
        session,
        user_id=user_id,
        vin=vin,
        fingerprint=fingerprint,
        market=normalized_market,
    )


async def create_vin_identity_user_vehicle(
    session: AsyncSession,
    *,
    user_id: UUID,
    payload: VinUserVehicleCreate,
) -> UserVehicle:
    """Save VIN-derived vehicle identity without retaining the VIN itself.

    This route intentionally bypasses VIN encryption, fingerprints, last-six
    storage, and decode-cache persistence. It exists so a successfully decoded
    identity can still become a private garage vehicle when protected VIN storage
    is not configured. The normal /vin save remains the only path that stores a
    recoverable VIN and therefore continues to fail closed without crypto keys.
    """

    vin = validate_vin(payload.vin)
    try:
        normalized_market = canonical_market(payload.market)
    except VehicleIdentityError as exc:
        raise PartGraphError(
            code=ErrorCode.REQUEST_VALIDATION_FAILED,
            message=str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        ) from exc

    resolved = await _decode_provider_without_persistence(
        session,
        vin=vin,
        market=normalized_market,
    )
    canonical_configuration_id = (
        resolved.matches[0].id if resolved.resolution == "matched" else None
    )
    vehicle = UserVehicle(
        user_id=user_id,
        canonical_configuration_id=canonical_configuration_id,
        nickname=payload.nickname,
        identity_source="vin",
        identity_resolution=resolved.resolution,
        identity_snapshot=resolved.identity.model_dump(mode="json"),
        decoder_provider=resolved.provider,
        decoder_observed_at=resolved.observed_at,
    )
    session.add(vehicle)
    await session.flush()
    return vehicle
