from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import ErrorCode, ErrorEnvelope, PartGraphError
from ..identity.auth.dependencies import AuthSessionDep, require_csrf
from ..identity.auth.roles import CuratorUserDep, assume_materializer_database_role
from ..identity.vehicle.models import VehicleConfiguration
from ..identity.vehicle.schemas import VehicleConfigurationInput
from ..identity.vehicle.taxonomy import canonicalize_fields, comparison_key
from .claim_locks import lock_mechanical_claims
from .fitment import PartFitment
from .models import CatalogSource, MechanicalClaim
from .parts import ComponentPartRole
from .provenance import CanonicalConflict, CanonicalRecordEvidence, CanonicalRecordVersion
from .repair_materialization_contract import IDEMPOTENCY_PATTERN, invalid_materialization
from .source_policy import (
    ClaimDomain,
    ClaimRisk,
    PromotionDecision,
    SourceClass,
    assess_mechanical_claim,
    load_source_authority_policy,
)

CanonicalClaimDomain = Literal["vehicle_identity", "part_fitment"]
CanonicalDomain = Literal["vehicle_identity", "fitment"]
CanonicalRecordType = Literal["vehicle_configuration", "part_fitment"]

_OPTIONAL_IDENTITY_FIELDS = (
    "generation",
    "trim",
    "body_style",
    "engine",
    "transmission",
    "drivetrain",
)
_STRUCTURED_IDENTITY_FIELDS = frozenset({"engine", "transmission"})


class PartFitmentClaimPayload(BaseModel):
    component_part_role_id: UUID
    applicability_state: Literal["applicable", "excluded", "conditional"]
    qualifier_key: str = Field(default="", max_length=128)
    qualifiers: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_scope(self) -> PartFitmentClaimPayload:
        self.qualifier_key = self.qualifier_key.strip()
        if self.applicability_state == "conditional" and not self.qualifier_key:
            raise ValueError("conditional fitment requires qualifier_key")
        return self


class CanonicalClaimMaterializationRead(BaseModel):
    mechanical_claim_id: UUID
    claim_domain: CanonicalClaimDomain
    canonical_domain: CanonicalDomain
    record_type: CanonicalRecordType
    record_id: UUID
    vehicle_configuration_id: UUID
    canonical_record_version_id: UUID
    version: int
    idempotent: bool = False


router = APIRouter(
    tags=["Knowledge Curation"],
    responses={
        401: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope},
        409: {"model": ErrorEnvelope},
        422: {"model": ErrorEnvelope},
        500: {"model": ErrorEnvelope},
    },
)
CsrfDep = Depends(require_csrf)
IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$",
    ),
]


def _detail_tokens(field: str, value: str) -> set[str]:
    return {token for token in comparison_key(field, value).split("|") if token}


def _compatible_identity_value(
    field: str,
    current: str | None,
    incoming: str | None,
) -> bool:
    if current is None or incoming is None:
        return True
    if field in _STRUCTURED_IDENTITY_FIELDS:
        current_tokens = _detail_tokens(field, current)
        incoming_tokens = _detail_tokens(field, incoming)
        return current_tokens <= incoming_tokens or incoming_tokens <= current_tokens
    return comparison_key(field, current) == comparison_key(field, incoming)


def _configuration_matches_identity_payload(
    configuration: VehicleConfiguration,
    payload: VehicleConfigurationInput,
) -> bool:
    incoming = canonicalize_fields(**payload.model_dump())
    if configuration.year != incoming["year"]:
        return False
    if configuration.market != incoming["market"]:
        return False
    if configuration.make != incoming["make"]:
        return False
    if comparison_key("model", configuration.model) != comparison_key(
        "model", str(incoming["model"])
    ):
        return False
    return all(
        _compatible_identity_value(
            field,
            getattr(configuration, field),
            incoming[field] if isinstance(incoming[field], str) else None,
        )
        for field in _OPTIONAL_IDENTITY_FIELDS
    )


def _claim_fully_covers_unverified_configuration(
    configuration: VehicleConfiguration,
    payload: VehicleConfigurationInput,
) -> bool:
    for field in _OPTIONAL_IDENTITY_FIELDS:
        stored = getattr(configuration, field)
        claimed = getattr(payload, field)
        if (stored is None) != (claimed is None):
            return False
    return True


def _request_sha256(claim: MechanicalClaim) -> str:
    payload = json.dumps(
        {
            "mechanical_claim_id": str(claim.id),
            "claim_domain": claim.claim_domain,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _canonical_target(claim: MechanicalClaim) -> tuple[CanonicalDomain, CanonicalRecordType]:
    if claim.claim_domain == ClaimDomain.VEHICLE_IDENTITY.value:
        return "vehicle_identity", "vehicle_configuration"
    if claim.claim_domain == ClaimDomain.PART_FITMENT.value:
        return "fitment", "part_fitment"
    if claim.claim_domain == ClaimDomain.SAFETY_CAMPAIGN.value:
        raise invalid_materialization(
            "Safety-campaign claims remain reviewed claim context and have no canonical materializer."
        )
    if claim.claim_domain in {
        ClaimDomain.REPAIR_REQUIREMENT.value,
        ClaimDomain.REPAIR_PROCEDURE.value,
    }:
        raise invalid_materialization(
            "Repair claims must be materialized through the repair-definition materializer."
        )
    raise invalid_materialization("Mechanical claim belongs to an unsupported materialization domain.")


async def _assert_claim_publishable(
    db: AsyncSession,
    claim: MechanicalClaim,
) -> None:
    if claim.promotion_state != "verified":
        raise invalid_materialization("Canonical materialization requires a verified mechanical claim.")
    if not claim.explicit_claim or not claim.exact_applicability:
        raise invalid_materialization(
            "Canonical materialization requires explicit exact-applicability evidence."
        )
    if claim.vehicle_configuration_id is None:
        raise invalid_materialization(
            "Canonical materialization requires an exact vehicle configuration."
        )

    source = await db.get(CatalogSource, claim.source_id)
    if source is None:
        raise invalid_materialization(
            "Mechanical claim references an unavailable source registry entry."
        )
    if source.license_status != "approved":
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_SOURCE_NOT_APPROVED,
            message="Supporting claim source must remain approved at publication time.",
            status_code=status.HTTP_409_CONFLICT,
        )

    try:
        source_class = SourceClass(source.source_class)
        claim_domain = ClaimDomain(claim.claim_domain)
        claim_risk = ClaimRisk(claim.claim_risk)
    except ValueError as exc:
        raise invalid_materialization(
            "Mechanical claim has an unsupported source-authority scope."
        ) from exc

    policy = await load_source_authority_policy(
        db,
        source_class=source_class,
        claim_domain=claim_domain,
        risk=claim_risk,
    )
    assessment = assess_mechanical_claim(
        policy=policy,
        source_class=source_class,
        claim_domain=claim_domain,
        exact_applicability=claim.exact_applicability,
        explicit_claim=claim.explicit_claim,
        risk=claim_risk,
        has_conflict=False,
    )
    if assessment.decision is PromotionDecision.CANDIDATE_ONLY:
        raise invalid_materialization(
            "Current source-authority policy does not permit canonical publication."
        )

    if claim.conflict_key is not None:
        conflict = await db.scalar(
            select(CanonicalConflict).where(
                CanonicalConflict.conflict_key == claim.conflict_key,
                CanonicalConflict.conflict_state.in_(("open", "blocked")),
            )
        )
        if conflict is not None:
            raise invalid_materialization(
                "Mechanical claim still has an unresolved canonical conflict."
            )


async def _existing_idempotent_publication(
    db: AsyncSession,
    *,
    claim: MechanicalClaim,
    idempotency_key: str,
    request_digest: str,
) -> CanonicalClaimMaterializationRead | None:
    existing = await db.scalar(
        select(CanonicalRecordVersion).where(
            CanonicalRecordVersion.idempotency_key == idempotency_key
        )
    )
    if existing is None:
        return None
    if existing.request_sha256 != request_digest:
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_PUBLICATION_IDEMPOTENCY_CONFLICT,
            message="Idempotency key was already used with a different publication request.",
            status_code=status.HTTP_409_CONFLICT,
        )

    canonical_domain, record_type = _canonical_target(claim)
    if existing.canonical_domain != canonical_domain or existing.record_type != record_type:
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_PUBLICATION_IDEMPOTENCY_CONFLICT,
            message="Idempotency key is bound to a different canonical publication target.",
            status_code=status.HTTP_409_CONFLICT,
        )
    evidence = await db.scalar(
        select(CanonicalRecordEvidence).where(
            CanonicalRecordEvidence.record_version_id == existing.id,
            CanonicalRecordEvidence.mechanical_claim_id == claim.id,
        )
    )
    if evidence is None:
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_PUBLICATION_IDEMPOTENCY_CONFLICT,
            message="Idempotency publication does not contain the requested supporting claim.",
            status_code=status.HTTP_409_CONFLICT,
        )
    assert claim.vehicle_configuration_id is not None
    return CanonicalClaimMaterializationRead(
        mechanical_claim_id=claim.id,
        claim_domain=claim.claim_domain,
        canonical_domain=canonical_domain,
        record_type=record_type,
        record_id=existing.record_id,
        vehicle_configuration_id=claim.vehicle_configuration_id,
        canonical_record_version_id=existing.id,
        version=existing.version,
        idempotent=True,
    )


async def _existing_claim_publication(
    db: AsyncSession,
    *,
    claim: MechanicalClaim,
    canonical_domain: CanonicalDomain,
    record_type: CanonicalRecordType,
) -> CanonicalClaimMaterializationRead | None:
    versions = list(
        await db.scalars(
            select(CanonicalRecordVersion)
            .join(
                CanonicalRecordEvidence,
                CanonicalRecordEvidence.record_version_id == CanonicalRecordVersion.id,
            )
            .where(
                CanonicalRecordEvidence.mechanical_claim_id == claim.id,
                CanonicalRecordVersion.canonical_domain == canonical_domain,
                CanonicalRecordVersion.record_type == record_type,
            )
            .order_by(CanonicalRecordVersion.version.desc())
        )
    )
    if not versions:
        return None
    current = next(
        (version for version in versions if version.publication_state == "verified"),
        None,
    )
    if current is None:
        raise invalid_materialization(
            "Mechanical claim was already used by a superseded canonical publication and cannot be replayed."
        )
    assert claim.vehicle_configuration_id is not None
    return CanonicalClaimMaterializationRead(
        mechanical_claim_id=claim.id,
        claim_domain=claim.claim_domain,
        canonical_domain=canonical_domain,
        record_type=record_type,
        record_id=current.record_id,
        vehicle_configuration_id=claim.vehicle_configuration_id,
        canonical_record_version_id=current.id,
        version=current.version,
        idempotent=True,
    )


async def _publish_record_version(
    db: AsyncSession,
    *,
    claim: MechanicalClaim,
    canonical_domain: CanonicalDomain,
    record_type: CanonicalRecordType,
    record_id: UUID,
    actor: str,
    idempotency_key: str,
    request_digest: str,
) -> CanonicalClaimMaterializationRead:
    current_versions = list(
        await db.scalars(
            select(CanonicalRecordVersion)
            .where(
                CanonicalRecordVersion.canonical_domain == canonical_domain,
                CanonicalRecordVersion.record_type == record_type,
                CanonicalRecordVersion.record_id == record_id,
                CanonicalRecordVersion.publication_state == "verified",
            )
            .with_for_update()
        )
    )
    if len(current_versions) > 1:
        raise invalid_materialization(
            "Canonical record contains multiple current verified publication envelopes."
        )
    previous = current_versions[0] if current_versions else None
    maximum_version = await db.scalar(
        select(func.max(CanonicalRecordVersion.version)).where(
            CanonicalRecordVersion.canonical_domain == canonical_domain,
            CanonicalRecordVersion.record_type == record_type,
            CanonicalRecordVersion.record_id == record_id,
        )
    )
    next_version = int(maximum_version or 0) + 1
    if previous is not None:
        previous.publication_state = "superseded"
        await db.flush()

    now = datetime.now(UTC)
    record_version = CanonicalRecordVersion(
        id=uuid4(),
        canonical_domain=canonical_domain,
        record_type=record_type,
        record_id=record_id,
        version=next_version,
        publication_state="verified",
        supersedes_version_id=previous.id if previous is not None else None,
        idempotency_key=idempotency_key,
        request_sha256=request_digest,
        published_by=actor,
        published_at=now,
    )
    db.add(record_version)
    await db.flush()
    db.add(
        CanonicalRecordEvidence(
            record_version_id=record_version.id,
            verified_evidence_id=claim.verified_evidence_id,
            mechanical_claim_id=claim.id,
            evidence_role="supports",
        )
    )
    await db.flush()

    assert claim.vehicle_configuration_id is not None
    return CanonicalClaimMaterializationRead(
        mechanical_claim_id=claim.id,
        claim_domain=claim.claim_domain,
        canonical_domain=canonical_domain,
        record_type=record_type,
        record_id=record_id,
        vehicle_configuration_id=claim.vehicle_configuration_id,
        canonical_record_version_id=record_version.id,
        version=record_version.version,
    )


async def _materialize_vehicle_identity(
    db: AsyncSession,
    *,
    claim: MechanicalClaim,
    actor: str,
    idempotency_key: str,
    request_digest: str,
) -> CanonicalClaimMaterializationRead:
    assert claim.vehicle_configuration_id is not None
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"canonical-vehicle:{claim.vehicle_configuration_id}"},
    )
    configuration = await db.get(VehicleConfiguration, claim.vehicle_configuration_id)
    if configuration is None:
        raise invalid_materialization(
            "Vehicle-identity claim references an unknown vehicle configuration."
        )
    try:
        payload = VehicleConfigurationInput.model_validate(claim.claim_payload)
    except ValidationError as exc:
        raise invalid_materialization(
            "Vehicle-identity claim payload is not a valid vehicle configuration identity.",
            details={"validation": exc.errors(include_url=False)},
        ) from exc
    if not _configuration_matches_identity_payload(configuration, payload):
        raise invalid_materialization(
            "Vehicle-identity claim contradicts the referenced canonical configuration."
        )

    existing = await _existing_claim_publication(
        db,
        claim=claim,
        canonical_domain="vehicle_identity",
        record_type="vehicle_configuration",
    )
    if existing is not None:
        return existing

    if configuration.verification_status == "unverified":
        if not _claim_fully_covers_unverified_configuration(configuration, payload):
            raise invalid_materialization(
                "An unverified vehicle configuration can only be verified by evidence covering every stored identity field."
            )
        configuration.verification_status = "verified"
        await db.flush()
    elif configuration.verification_status != "verified":
        raise invalid_materialization(
            "Vehicle configuration has an unsupported verification state."
        )

    return await _publish_record_version(
        db,
        claim=claim,
        canonical_domain="vehicle_identity",
        record_type="vehicle_configuration",
        record_id=configuration.id,
        actor=actor,
        idempotency_key=idempotency_key,
        request_digest=request_digest,
    )


async def _materialize_part_fitment(
    db: AsyncSession,
    *,
    claim: MechanicalClaim,
    actor: str,
    idempotency_key: str,
    request_digest: str,
) -> CanonicalClaimMaterializationRead:
    assert claim.vehicle_configuration_id is not None
    try:
        payload = PartFitmentClaimPayload.model_validate(claim.claim_payload)
    except ValidationError as exc:
        raise invalid_materialization(
            "Part-fitment claim payload is invalid.",
            details={"validation": exc.errors(include_url=False)},
        ) from exc

    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {
            "key": (
                f"canonical-fitment:{claim.vehicle_configuration_id}:"
                f"{payload.component_part_role_id}:{payload.qualifier_key}"
            )
        },
    )
    if await db.get(VehicleConfiguration, claim.vehicle_configuration_id) is None:
        raise invalid_materialization(
            "Part-fitment claim references an unknown vehicle configuration."
        )
    if await db.get(ComponentPartRole, payload.component_part_role_id) is None:
        raise invalid_materialization(
            "Part-fitment claim references an unknown canonical component/part role."
        )

    existing_publication = await _existing_claim_publication(
        db,
        claim=claim,
        canonical_domain="fitment",
        record_type="part_fitment",
    )
    if existing_publication is not None:
        return existing_publication

    fitment = await db.scalar(
        select(PartFitment).where(
            PartFitment.vehicle_configuration_id == claim.vehicle_configuration_id,
            PartFitment.component_part_role_id == payload.component_part_role_id,
            PartFitment.qualifier_key == payload.qualifier_key,
        )
    )
    if fitment is None:
        fitment = PartFitment(
            id=uuid4(),
            vehicle_configuration_id=claim.vehicle_configuration_id,
            component_part_role_id=payload.component_part_role_id,
            applicability_state=payload.applicability_state,
            qualifier_key=payload.qualifier_key,
            qualifiers=payload.qualifiers,
        )
        db.add(fitment)
        await db.flush()
    elif (
        fitment.applicability_state != payload.applicability_state
        or fitment.qualifiers != payload.qualifiers
    ):
        raise invalid_materialization(
            "Verified claim conflicts with an existing canonical fitment row; canonical fitment is not overwritten automatically."
        )

    return await _publish_record_version(
        db,
        claim=claim,
        canonical_domain="fitment",
        record_type="part_fitment",
        record_id=fitment.id,
        actor=actor,
        idempotency_key=idempotency_key,
        request_digest=request_digest,
    )


async def materialize_verified_mechanical_claim_service(
    db: AsyncSession,
    *,
    claim_id: UUID,
    actor: str,
    idempotency_key: str,
) -> CanonicalClaimMaterializationRead:
    await lock_mechanical_claims(db, [claim_id], shared=True)
    claim = await db.get(MechanicalClaim, claim_id)
    if claim is None:
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_MATERIALIZATION_INVALID,
            message="Mechanical claim not found for canonical materialization.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    canonical_domain, record_type = _canonical_target(claim)
    await _assert_claim_publishable(db, claim)
    request_digest = _request_sha256(claim)
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"canonical-publication:{idempotency_key}"},
    )
    existing = await _existing_idempotent_publication(
        db,
        claim=claim,
        idempotency_key=idempotency_key,
        request_digest=request_digest,
    )
    if existing is not None:
        return existing

    if canonical_domain == "vehicle_identity" and record_type == "vehicle_configuration":
        return await _materialize_vehicle_identity(
            db,
            claim=claim,
            actor=actor,
            idempotency_key=idempotency_key,
            request_digest=request_digest,
        )
    if canonical_domain == "fitment" and record_type == "part_fitment":
        return await _materialize_part_fitment(
            db,
            claim=claim,
            actor=actor,
            idempotency_key=idempotency_key,
            request_digest=request_digest,
        )
    raise invalid_materialization("Mechanical claim has no supported canonical materializer.")


@router.post(
    "/mechanical-claims/{claim_id}/materialize",
    response_model=CanonicalClaimMaterializationRead,
    dependencies=[CsrfDep],
)
async def materialize_verified_mechanical_claim(
    claim_id: UUID,
    user: CuratorUserDep,
    db: AuthSessionDep,
    idempotency_key: IdempotencyKey,
) -> CanonicalClaimMaterializationRead:
    await assume_materializer_database_role(db)
    if IDEMPOTENCY_PATTERN.fullmatch(idempotency_key) is None:
        raise invalid_materialization("Idempotency-Key is invalid.")
    return await materialize_verified_mechanical_claim_service(
        db,
        claim_id=claim_id,
        actor=f"{user.id}:{user.role}",
        idempotency_key=idempotency_key,
    )
