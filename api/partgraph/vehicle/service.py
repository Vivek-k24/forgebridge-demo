from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .models import VehicleConfiguration
from .schemas import VehicleConfigurationInput

OPTIONAL_IDENTITY_FIELDS = (
    "generation",
    "trim",
    "body_style",
    "engine",
    "transmission",
    "drivetrain",
)

ALIASES: dict[str, dict[str, str]] = {
    "market": {
        "u.s.": "us",
        "usa": "us",
        "united states": "us",
    },
    "body_style": {
        "4 dr sedan": "sedan",
        "4 door sedan": "sedan",
        "4-door sedan": "sedan",
        "sedan 4d": "sedan",
    },
    "transmission": {
        "continuously variable transmission": "cvt",
    },
    "drivetrain": {
        "front wheel drive": "fwd",
        "front-wheel drive": "fwd",
    },
}


class VehicleIdentityAmbiguousError(Exception):
    pass


def _canonical(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.casefold().split())


def _canonical_field(field: str, value: str | None) -> str:
    canonical = _canonical(value)
    return ALIASES.get(field, {}).get(canonical, canonical)


def _digest(parts: tuple[str, ...]) -> str:
    return sha256("\x1f".join(parts).encode()).hexdigest()


def base_identity_hash(payload: VehicleConfigurationInput) -> str:
    return _digest(
        (
            str(payload.year),
            _canonical_field("market", payload.market),
            _canonical_field("make", payload.make),
            _canonical_field("model", payload.model),
        )
    )


def identity_hash(payload: VehicleConfigurationInput) -> str:
    return _digest(
        (
            str(payload.year),
            _canonical_field("market", payload.market),
            _canonical_field("make", payload.make),
            _canonical_field("model", payload.model),
            _canonical_field("generation", payload.generation),
            _canonical_field("trim", payload.trim),
            _canonical_field("body_style", payload.body_style),
            _canonical_field("engine", payload.engine),
            _canonical_field("transmission", payload.transmission),
            _canonical_field("drivetrain", payload.drivetrain),
        )
    )


def _compatible(
    existing: VehicleConfiguration,
    payload: VehicleConfigurationInput,
) -> bool:
    for field in OPTIONAL_IDENTITY_FIELDS:
        existing_value = _canonical_field(field, getattr(existing, field))
        incoming_value = _canonical_field(field, getattr(payload, field))
        if existing_value and incoming_value and existing_value != incoming_value:
            return False
    return True


def _match_score(
    existing: VehicleConfiguration,
    payload: VehicleConfigurationInput,
) -> int:
    score = 0
    for field in OPTIONAL_IDENTITY_FIELDS:
        existing_value = _canonical_field(field, getattr(existing, field))
        incoming_value = _canonical_field(field, getattr(payload, field))
        if existing_value and incoming_value and existing_value == incoming_value:
            score += 1
    return score


def _merged_payload(
    existing: VehicleConfiguration,
    payload: VehicleConfigurationInput,
) -> VehicleConfigurationInput:
    merged = {
        "year": existing.year,
        "market": existing.market,
        "make": existing.make,
        "model": existing.model,
    }
    for field in OPTIONAL_IDENTITY_FIELDS:
        existing_value = getattr(existing, field)
        incoming_value = getattr(payload, field)
        merged[field] = existing_value if existing_value is not None else incoming_value
    return VehicleConfigurationInput(**merged)


async def _resolve_compatible_candidate(
    session: AsyncSession,
    payload: VehicleConfigurationInput,
) -> VehicleConfiguration | None:
    candidates = list(
        await session.scalars(
            select(VehicleConfiguration).where(
                VehicleConfiguration.base_identity_hash == base_identity_hash(payload)
            )
        )
    )
    compatible = [candidate for candidate in candidates if _compatible(candidate, payload)]
    if not compatible:
        return None
    if len(compatible) == 1:
        return compatible[0]

    ranked = sorted(
        ((_match_score(candidate, payload), candidate) for candidate in compatible),
        key=lambda item: item[0],
        reverse=True,
    )
    if len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
        raise VehicleIdentityAmbiguousError(
            "vehicle identity is ambiguous; provide more configuration details"
        )
    return ranked[0][1]


async def create_or_get_configuration(
    session: AsyncSession,
    payload: VehicleConfigurationInput,
) -> tuple[VehicleConfiguration, str]:
    fingerprint = identity_hash(payload)
    exact = await session.scalar(
        select(VehicleConfiguration).where(VehicleConfiguration.identity_hash == fingerprint)
    )
    if exact is not None:
        return exact, "matched"

    existing = await _resolve_compatible_candidate(session, payload)
    if existing is not None:
        merged_payload = _merged_payload(existing, payload)
        merged_hash = identity_hash(merged_payload)
        enriched = False

        for field in OPTIONAL_IDENTITY_FIELDS:
            if getattr(existing, field) is None and getattr(payload, field) is not None:
                setattr(existing, field, getattr(payload, field))
                enriched = True

        if enriched:
            duplicate = await session.scalar(
                select(VehicleConfiguration).where(
                    VehicleConfiguration.identity_hash == merged_hash,
                    VehicleConfiguration.id != existing.id,
                )
            )
            if duplicate is not None:
                await session.rollback()
                return duplicate, "matched"
            existing.identity_hash = merged_hash
            await session.commit()
            await session.refresh(existing)
            return existing, "enriched"

        return existing, "matched"

    configuration = VehicleConfiguration(
        base_identity_hash=base_identity_hash(payload),
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
        exact = await session.scalar(
            select(VehicleConfiguration).where(VehicleConfiguration.identity_hash == fingerprint)
        )
        if exact is None:
            raise
        return exact, "matched"

    await session.refresh(configuration)
    return configuration, "created"


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
