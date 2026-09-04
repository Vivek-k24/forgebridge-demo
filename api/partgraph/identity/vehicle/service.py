from hashlib import sha256
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .model_catalog import models_for_make_year
from .models import VehicleConfiguration, VehicleSpecificationProfile
from .schemas import VehicleConfigurationInput, VehicleSelectionInput
from .taxonomy import (
    CANONICALIZATION_VERSION,
    canonical_body_style,
    canonical_drivetrain,
    canonical_engine,
    canonical_generation,
    canonical_make,
    canonical_market,
    canonical_model,
    canonical_transmission,
    canonical_trim,
    canonicalize_fields,
    compact_key,
    comparison_key,
)
from .trim_catalog import trims_for_vehicle

OPTIONAL_IDENTITY_FIELDS = (
    "generation",
    "trim",
    "body_style",
    "engine",
    "transmission",
    "drivetrain",
)
STRUCTURED_DETAIL_FIELDS = {"engine", "transmission"}
SELECTION_DETAIL_FIELDS = ("body_style", "engine", "transmission", "drivetrain")


class AmbiguousVehicleIdentityError(ValueError):
    pass


def _hash(parts: tuple[str, ...]) -> str:
    return sha256("\x1f".join(parts).encode()).hexdigest()


def _base_hash(values: dict[str, int | str | None]) -> str:
    return _hash(
        (
            str(values["year"]),
            str(values["market"]),
            str(values["make"]),
            comparison_key("model", str(values["model"])),
        )
    )


def _identity_hash(values: dict[str, int | str | None]) -> str:
    parts = [
        str(values["year"]),
        str(values["market"]),
        str(values["make"]),
        comparison_key("model", str(values["model"])),
    ]
    parts.extend(
        comparison_key(field, values[field] if isinstance(values[field], str) else None)
        for field in OPTIONAL_IDENTITY_FIELDS
    )
    return _hash(tuple(parts))


def _detail_tokens(field: str, value: str) -> set[str]:
    return {token for token in comparison_key(field, value).split("|") if token}


def _compatible(field: str, current: str | None, incoming: str | None) -> bool:
    if current is None or incoming is None:
        return True
    if field in STRUCTURED_DETAIL_FIELDS:
        current_tokens = _detail_tokens(field, current)
        incoming_tokens = _detail_tokens(field, incoming)
        return current_tokens <= incoming_tokens or incoming_tokens <= current_tokens
    return comparison_key(field, current) == comparison_key(field, incoming)


def _candidate_score(
    candidate: VehicleConfiguration,
    incoming: dict[str, int | str | None],
) -> tuple[int, int]:
    matched = 0
    specificity = 0
    for field in OPTIONAL_IDENTITY_FIELDS:
        current = getattr(candidate, field)
        supplied = incoming[field]
        if current is not None:
            specificity += 1
        if current is not None and isinstance(supplied, str):
            if _compatible(field, current, supplied):
                matched += 1
    return matched, specificity


def _candidate_is_compatible(
    candidate: VehicleConfiguration,
    incoming: dict[str, int | str | None],
) -> bool:
    return all(
        _compatible(
            field,
            getattr(candidate, field),
            incoming[field] if isinstance(incoming[field], str) else None,
        )
        for field in OPTIONAL_IDENTITY_FIELDS
    )


def _merge_candidate(
    candidate: VehicleConfiguration,
    incoming: dict[str, int | str | None],
) -> bool:
    changed = False
    for field in OPTIONAL_IDENTITY_FIELDS:
        current = getattr(candidate, field)
        supplied = incoming[field]
        if not isinstance(supplied, str):
            continue
        if current is None:
            setattr(candidate, field, supplied)
            changed = True
            continue
        if field in STRUCTURED_DETAIL_FIELDS:
            current_tokens = _detail_tokens(field, current)
            incoming_tokens = _detail_tokens(field, supplied)
            if current_tokens < incoming_tokens:
                setattr(candidate, field, supplied)
                changed = True
    return changed


async def _lock_base_identity(session: AsyncSession, base_hash: str) -> None:
    unsigned = int(base_hash[:16], 16)
    signed = unsigned if unsigned < 2**63 else unsigned - 2**64
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": signed},
    )


async def resolve_configuration(
    session: AsyncSession,
    payload: VehicleConfigurationInput,
) -> tuple[VehicleConfiguration, str]:
    """Internal canonical write path used by verified ingestion/tests, not the public UI."""
    incoming = canonicalize_fields(**payload.model_dump())
    base_hash = _base_hash(incoming)
    fingerprint = _identity_hash(incoming)

    await _lock_base_identity(session, base_hash)

    exact = await session.scalar(
        select(VehicleConfiguration).where(VehicleConfiguration.identity_hash == fingerprint)
    )
    if exact is not None:
        return exact, "matched"

    candidates = list(
        await session.scalars(
            select(VehicleConfiguration)
            .where(VehicleConfiguration.base_identity_hash == base_hash)
            .with_for_update()
        )
    )
    compatible = [
        candidate for candidate in candidates if _candidate_is_compatible(candidate, incoming)
    ]

    if compatible:
        scores = {candidate.id: _candidate_score(candidate, incoming) for candidate in compatible}
        best_score = max(scores.values())
        best = [candidate for candidate in compatible if scores[candidate.id] == best_score]
        if len(best) != 1:
            await session.rollback()
            raise AmbiguousVehicleIdentityError(
                "Multiple stored configurations are compatible. Add trim, body, engine, "
                "transmission, drivetrain, or generation detail before continuing."
            )

        candidate = best[0]
        changed = _merge_candidate(candidate, incoming)
        if changed:
            values = {
                "year": candidate.year,
                "market": candidate.market,
                "make": candidate.make,
                "model": candidate.model,
                **{field: getattr(candidate, field) for field in OPTIONAL_IDENTITY_FIELDS},
            }
            candidate.identity_hash = _identity_hash(values)
            candidate.canonicalization_version = CANONICALIZATION_VERSION
            await session.commit()
            await session.refresh(candidate)
            return candidate, "enriched"
        return candidate, "matched"

    configuration = VehicleConfiguration(
        identity_hash=fingerprint,
        base_identity_hash=base_hash,
        canonicalization_version=CANONICALIZATION_VERSION,
        **incoming,
        identity_source="manual",
        verification_status="unverified",
    )
    session.add(configuration)
    await session.commit()
    await session.refresh(configuration)
    return configuration, "created"


async def _selection_base_candidates(
    session: AsyncSession,
    *,
    year: int,
    market: str,
    make: str,
) -> list[VehicleConfiguration]:
    normalized_market = canonical_market(market)
    normalized_make = canonical_make(make)
    rows = await session.scalars(
        select(VehicleConfiguration).where(
            VehicleConfiguration.year == year,
            VehicleConfiguration.market == normalized_market,
            VehicleConfiguration.make == normalized_make,
        )
    )
    return list(rows)


def _filter_values(values: set[str], query: str | None) -> list[str]:
    if query:
        query_key = compact_key(query)
        values = {value for value in values if query_key in compact_key(value)}
    return sorted(values, key=str.casefold)


def _filter_query(values: set[str], query: str | None, limit: int) -> list[str]:
    return _filter_values(values, query)[:limit]


async def list_model_options(
    session: AsyncSession,
    *,
    year: int,
    market: str,
    make: str,
    query: str | None,
) -> list[str]:
    # Validate the PartGraph market/make boundary first. vPIC is used only as a
    # complete model discovery source; these values do not become canonical rows.
    canonical_market(market)
    normalized_make = canonical_make(make)
    models = set(await models_for_make_year(year=year, make=normalized_make))

    # Keep already-reviewed/private-test canonical model labels discoverable too,
    # while never writing provider discovery values into VehicleConfiguration.
    candidates = await _selection_base_candidates(
        session,
        year=year,
        market=market,
        make=normalized_make,
    )
    models.update(candidate.model for candidate in candidates)
    return _filter_values(models, query)


async def list_trim_options(
    session: AsyncSession,
    *,
    year: int,
    market: str,
    make: str,
    model: str,
    query: str | None,
) -> list[str]:
    # CarsXE is used only for consumer-facing trim discovery. PartGraph's market
    # boundary is still validated here, and provider values never create shared
    # VehicleConfiguration rows.
    canonical_market(market)
    normalized_make = canonical_make(make)
    normalized_model = canonical_model(model)
    values = set(
        await trims_for_vehicle(
            year=year,
            make=normalized_make,
            model=normalized_model,
        )
    )

    # Preserve reviewed canonical labels as a union so a verified PartGraph trim
    # is never hidden when an external catalog omits or names it differently.
    candidates = await _selection_base_candidates(
        session,
        year=year,
        market=market,
        make=normalized_make,
    )
    model_key = comparison_key("model", normalized_model)
    values.update(
        candidate.trim
        for candidate in candidates
        if candidate.trim is not None and comparison_key("model", candidate.model) == model_key
    )
    return _filter_values(values, query)


async def list_generation_options(
    session: AsyncSession,
    *,
    year: int,
    market: str,
    make: str,
    model: str,
    trim: str | None,
    query: str | None,
    limit: int,
) -> list[str]:
    candidates = await _selection_base_candidates(
        session,
        year=year,
        market=market,
        make=make,
    )
    model_key = comparison_key("model", canonical_model(model))
    trim_key = comparison_key("trim", canonical_trim(trim)) if trim else None
    values = {
        candidate.generation
        for candidate in candidates
        if candidate.generation is not None
        and comparison_key("model", candidate.model) == model_key
        and (
            trim_key is None
            or (
                candidate.trim is not None
                and comparison_key("trim", candidate.trim) == trim_key
            )
        )
    }
    return _filter_query(values, query, limit)


async def resolve_selection(
    session: AsyncSession,
    payload: VehicleSelectionInput,
) -> tuple[str, dict[str, int | str | None], list[VehicleConfiguration]]:
    """Resolve user/source text against canonical rows without mutating shared truth."""
    normalized = {
        "year": payload.year,
        "market": canonical_market(payload.market),
        "make": canonical_make(payload.make),
        "model": canonical_model(payload.model),
        "trim": canonical_trim(payload.trim),
        "generation": canonical_generation(payload.generation),
        "body_style": canonical_body_style(payload.body_style),
        "engine": canonical_engine(payload.engine),
        "transmission": canonical_transmission(payload.transmission),
        "drivetrain": canonical_drivetrain(payload.drivetrain),
    }
    candidates = await _selection_base_candidates(
        session,
        year=payload.year,
        market=payload.market,
        make=payload.make,
    )
    model_key = comparison_key("model", str(normalized["model"]))
    matches = [
        candidate
        for candidate in candidates
        if comparison_key("model", candidate.model) == model_key
    ]

    if isinstance(normalized["trim"], str):
        trim_key = comparison_key("trim", normalized["trim"])
        matches = [
            candidate
            for candidate in matches
            if candidate.trim is not None
            and comparison_key("trim", candidate.trim) == trim_key
        ]

    for field in SELECTION_DETAIL_FIELDS:
        incoming = normalized[field]
        if not isinstance(incoming, str):
            continue
        matches = [
            candidate
            for candidate in matches
            if _compatible(field, getattr(candidate, field), incoming)
        ]

    if not matches:
        return "manual_candidate", normalized, []
    if len(matches) == 1:
        return "matched", normalized, matches
    return "ambiguous", normalized, matches[:10]


async def get_configuration(
    session: AsyncSession,
    configuration_id: UUID,
) -> VehicleConfiguration | None:
    return await session.get(VehicleConfiguration, configuration_id)


async def get_specification_profile(
    session: AsyncSession,
    configuration_id: UUID,
) -> VehicleSpecificationProfile | None:
    return await session.scalar(
        select(VehicleSpecificationProfile).where(
            VehicleSpecificationProfile.vehicle_configuration_id == configuration_id
        )
    )


async def list_configurations(
    session: AsyncSession,
    limit: int,
) -> list[VehicleConfiguration]:
    rows = await session.scalars(
        select(VehicleConfiguration)
        .order_by(VehicleConfiguration.updated_at.desc())
        .limit(limit)
    )
    return list(rows)
