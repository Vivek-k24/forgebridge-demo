from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import ErrorCode, PartGraphError
from ..vehicle.taxonomy import VehicleIdentityError, canonical_market
from .crypto import VinCryptoError, vin_fingerprint
from .service import (
    ResolvedVin,
    _decode_validated_vin,
    _provider_snapshot,
    _resolve_identity_snapshot,
)
from .vin import decode_vin_values_extended, mask_vin, validate_vin


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
    persisted in that fallback path. Saving a VIN continues to use protect_vin()
    and therefore still requires the configured encryption keyring and lookup key.
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
        provider = await decode_vin_values_extended(vin)
        identity = _provider_snapshot(provider, normalized_market)
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

    return await _decode_validated_vin(
        session,
        user_id=user_id,
        vin=vin,
        fingerprint=fingerprint,
        market=normalized_market,
    )
