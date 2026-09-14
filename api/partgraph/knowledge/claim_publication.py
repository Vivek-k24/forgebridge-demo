from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ValidationError, model_validator
from sqlalchemy import select, text

from ..errors import ErrorCode, ErrorEnvelope, PartGraphError
from ..identity.auth.dependencies import AuthSessionDep, require_csrf
from ..identity.auth.roles import CuratorUserDep, assume_curator_database_role
from ..identity.vehicle.models import VehicleConfiguration
from .models import CatalogSource, CatalogVerifiedEvidence, MechanicalClaim
from .provenance import CanonicalConflict, CanonicalConflictItem
from .source_policy import (
    ClaimDomain,
    ClaimRisk,
    PromotionDecision,
    SourceClass,
    assess_mechanical_claim,
)

PromotionState = Literal[
    "needs_review",
    "verified",
    "conflict",
    "rejected",
    "superseded",
]
_CANONICAL_CONFLICT_DOMAINS: dict[ClaimDomain, str] = {
    ClaimDomain.VEHICLE_IDENTITY: "vehicle_identity",
    ClaimDomain.REPAIR_REQUIREMENT: "requirement",
    ClaimDomain.REPAIR_PROCEDURE: "procedure",
    ClaimDomain.PART_FITMENT: "fitment",
}


class VerifiedMechanicalClaimSpec(BaseModel):
    claim_domain: ClaimDomain
    claim_risk: ClaimRisk = ClaimRisk.NORMAL
    normalized_key: str
    claim_payload: dict[str, object]
    explicit_claim: bool
    exact_applicability: bool
    vehicle_configuration_id: UUID | None = None
    repair_key: str | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> VerifiedMechanicalClaimSpec:
        self.normalized_key = " ".join(self.normalized_key.split())
        if not self.normalized_key or len(self.normalized_key) > 160:
            raise ValueError("normalized_key must contain 1-160 characters")
        if not self.claim_payload:
            raise ValueError("claim_payload cannot be empty")
        if self.exact_applicability and self.vehicle_configuration_id is None:
            raise ValueError(
                "vehicle_configuration_id is required for exact applicability"
            )
        if self.claim_domain in {
            ClaimDomain.REPAIR_REQUIREMENT,
            ClaimDomain.REPAIR_PROCEDURE,
        }:
            if not self.repair_key:
                raise ValueError("repair_key is required for repair claims")
        elif self.repair_key is not None:
            raise ValueError("repair_key is only valid for repair claims")
        return self


class MechanicalClaimPublicationRead(BaseModel):
    mechanical_claim_id: UUID
    verified_evidence_id: UUID
    source_key: str
    promotion_state: PromotionState
    policy_decision: PromotionDecision
    policy_reason: str
    conflict_key: str
    canonical_conflict_id: UUID | None = None
    idempotent: bool = False


router = APIRouter(
    prefix="/api/v1/curation",
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


def _actor(user: CuratorUserDep) -> str:
    return f"{user.id}:{user.role}"


def _conflict_key(spec: VerifiedMechanicalClaimSpec) -> str:
    scope = {
        "claim_domain": spec.claim_domain.value,
        "vehicle_configuration_id": (
            str(spec.vehicle_configuration_id)
            if spec.vehicle_configuration_id is not None
            else None
        ),
        "repair_key": spec.repair_key,
        "normalized_key": spec.normalized_key,
    }
    digest = hashlib.sha256(
        json.dumps(scope, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"mechanical:{digest}"


def _same_fact(claim: MechanicalClaim, spec: VerifiedMechanicalClaimSpec) -> bool:
    return (
        claim.claim_payload == spec.claim_payload
        and claim.explicit_claim == spec.explicit_claim
        and claim.exact_applicability == spec.exact_applicability
        and claim.claim_risk == spec.claim_risk.value
    )


def _promotion_state(
    *,
    decision: PromotionDecision,
    exact_applicability: bool,
    explicit_claim: bool,
    has_conflict: bool,
) -> PromotionState:
    if has_conflict:
        return "conflict"
    if not exact_applicability or not explicit_claim:
        return "needs_review"
    if decision in {PromotionDecision.ELIGIBLE, PromotionDecision.HUMAN_REVIEW_REQUIRED}:
        # This endpoint is itself an explicit curator action, satisfying policy
        # cases that require human review. Exact applicability remains mandatory.
        return "verified"
    return "needs_review"


async def _ensure_vehicle_exists(
    db: AuthSessionDep,
    configuration_id: UUID | None,
) -> None:
    if configuration_id is None:
        return
    if await db.get(VehicleConfiguration, configuration_id) is None:
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_CANDIDATE_INVALID,
            message="Verified evidence references an unknown vehicle configuration.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


async def _conflict_record(
    db: AuthSessionDep,
    *,
    spec: VerifiedMechanicalClaimSpec,
    conflict_key: str,
    contender_ids: list[UUID],
) -> UUID | None:
    canonical_domain = _CANONICAL_CONFLICT_DOMAINS.get(spec.claim_domain)
    if canonical_domain is None:
        return None

    conflict = await db.scalar(
        select(CanonicalConflict).where(CanonicalConflict.conflict_key == conflict_key)
    )
    if conflict is None:
        conflict = CanonicalConflict(
            conflict_key=conflict_key,
            canonical_domain=canonical_domain,
            conflict_state="open",
        )
        db.add(conflict)
        await db.flush()
    else:
        if conflict.canonical_domain != canonical_domain:
            raise PartGraphError(
                code=ErrorCode.KNOWLEDGE_PUBLICATION_CONFLICT,
                message="Existing conflict record belongs to a different canonical domain.",
                status_code=status.HTTP_409_CONFLICT,
            )
        # A later contradictory claim reopens the same deterministic scope rather
        # than creating a second conflict or silently inheriting an old resolution.
        conflict.conflict_state = "open"
        conflict.resolution = None
        conflict.resolution_rationale = None
        conflict.resolved_at = None
        conflict.resolved_by = None

    for claim_id in contender_ids:
        existing_item = await db.scalar(
            select(CanonicalConflictItem).where(
                CanonicalConflictItem.conflict_id == conflict.id,
                CanonicalConflictItem.mechanical_claim_id == claim_id,
            )
        )
        if existing_item is None:
            db.add(
                CanonicalConflictItem(
                    conflict_id=conflict.id,
                    mechanical_claim_id=claim_id,
                    disposition="contender",
                )
            )
        else:
            existing_item.disposition = "contender"
    await db.flush()
    return conflict.id


@router.post(
    "/verified-evidence/{evidence_id}/publish-claim",
    response_model=MechanicalClaimPublicationRead,
    dependencies=[CsrfDep],
)
async def publish_verified_mechanical_claim(
    evidence_id: UUID,
    user: CuratorUserDep,
    db: AuthSessionDep,
) -> MechanicalClaimPublicationRead:
    await assume_curator_database_role(db)
    actor = _actor(user)

    # Serialize repeated publication attempts for the same evidence without
    # introducing a schema restriction that one evidence row can support only one claim forever.
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": str(evidence_id)},
    )

    evidence = await db.get(CatalogVerifiedEvidence, evidence_id)
    if evidence is None:
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_EVIDENCE_NOT_FOUND,
            message="Verified evidence not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if evidence.candidate_type != "mechanical_claim_candidate":
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_CANDIDATE_INVALID,
            message="Verified evidence is not a mechanical-claim candidate.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    raw_spec = evidence.verified_payload.get("mechanical_claim")
    if not isinstance(raw_spec, dict):
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_CANDIDATE_INVALID,
            message="Verified evidence does not contain a structured mechanical claim.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    try:
        spec = VerifiedMechanicalClaimSpec.model_validate(raw_spec)
    except ValidationError as exc:
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_CANDIDATE_INVALID,
            message="Verified evidence contains an invalid mechanical-claim scope.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"validation": exc.errors(include_url=False)},
        ) from exc

    source = await db.scalar(
        select(CatalogSource).where(CatalogSource.source_key == evidence.source_name)
    )
    if source is None:
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_SOURCE_NOT_FOUND,
            message="Verified evidence references an unregistered source.",
            status_code=status.HTTP_409_CONFLICT,
        )
    if source.source_class != evidence.source_type:
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_PUBLICATION_CONFLICT,
            message="Verified evidence source class no longer matches the source registry.",
            status_code=status.HTTP_409_CONFLICT,
        )
    if source.license_status != "approved":
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_SOURCE_NOT_APPROVED,
            message="The evidence source is not approved for canonical publication.",
            status_code=status.HTTP_409_CONFLICT,
        )

    await _ensure_vehicle_exists(db, spec.vehicle_configuration_id)
    if spec.exact_applicability:
        identity = evidence.vehicle_identity or {}
        if identity.get("vehicle_configuration_id") != str(spec.vehicle_configuration_id):
            raise PartGraphError(
                code=ErrorCode.KNOWLEDGE_PUBLICATION_CONFLICT,
                message="Exact applicability does not match the verified evidence vehicle identity.",
                status_code=status.HTTP_409_CONFLICT,
            )

    try:
        source_class = SourceClass(source.source_class)
    except ValueError as exc:
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_PUBLICATION_CONFLICT,
            message="The source registry contains an unsupported authority class.",
            status_code=status.HTTP_409_CONFLICT,
        ) from exc

    conflict_key = _conflict_key(spec)
    existing_from_evidence = await db.scalar(
        select(MechanicalClaim).where(
            MechanicalClaim.verified_evidence_id == evidence.id,
            MechanicalClaim.claim_domain == spec.claim_domain.value,
            MechanicalClaim.normalized_key == spec.normalized_key,
            MechanicalClaim.conflict_key == conflict_key,
        )
    )
    if existing_from_evidence is not None:
        assessment = assess_mechanical_claim(
            source_class=source_class,
            claim_domain=spec.claim_domain,
            exact_applicability=spec.exact_applicability,
            explicit_claim=spec.explicit_claim,
            risk=spec.claim_risk,
            has_conflict=existing_from_evidence.promotion_state == "conflict",
        )
        conflict = await db.scalar(
            select(CanonicalConflict).where(CanonicalConflict.conflict_key == conflict_key)
        )
        return MechanicalClaimPublicationRead(
            mechanical_claim_id=existing_from_evidence.id,
            verified_evidence_id=evidence.id,
            source_key=source.source_key,
            promotion_state=existing_from_evidence.promotion_state,
            policy_decision=assessment.decision,
            policy_reason=assessment.reason,
            conflict_key=conflict_key,
            canonical_conflict_id=conflict.id if conflict is not None else None,
            idempotent=True,
        )

    scoped_claims = list(
        await db.scalars(
            select(MechanicalClaim).where(
                MechanicalClaim.conflict_key == conflict_key,
                MechanicalClaim.promotion_state.in_(("verified", "conflict")),
            )
        )
    )
    contradictory = [claim for claim in scoped_claims if not _same_fact(claim, spec)]
    has_conflict = bool(contradictory) or any(
        claim.promotion_state == "conflict" for claim in scoped_claims
    )

    assessment = assess_mechanical_claim(
        source_class=source_class,
        claim_domain=spec.claim_domain,
        exact_applicability=spec.exact_applicability,
        explicit_claim=spec.explicit_claim,
        risk=spec.claim_risk,
        has_conflict=has_conflict,
    )
    promotion_state = _promotion_state(
        decision=assessment.decision,
        exact_applicability=spec.exact_applicability,
        explicit_claim=spec.explicit_claim,
        has_conflict=has_conflict,
    )
    now = datetime.now(UTC)
    claim = MechanicalClaim(
        source_id=source.id,
        verified_evidence_id=evidence.id,
        vehicle_configuration_id=spec.vehicle_configuration_id,
        claim_domain=spec.claim_domain.value,
        claim_risk=spec.claim_risk.value,
        normalized_key=spec.normalized_key,
        repair_key=spec.repair_key,
        claim_payload=spec.claim_payload,
        explicit_claim=spec.explicit_claim,
        exact_applicability=spec.exact_applicability,
        promotion_state=promotion_state,
        conflict_key=conflict_key,
        reviewed_at=now,
        reviewed_by=actor,
    )
    db.add(claim)
    await db.flush()

    conflict_id: UUID | None = None
    if has_conflict:
        for contender in scoped_claims:
            if contender.promotion_state == "verified":
                contender.promotion_state = "conflict"
                contender.reviewed_at = now
                contender.reviewed_by = actor
        await db.flush()
        conflict_id = await _conflict_record(
            db,
            spec=spec,
            conflict_key=conflict_key,
            contender_ids=[*(item.id for item in scoped_claims), claim.id],
        )

    return MechanicalClaimPublicationRead(
        mechanical_claim_id=claim.id,
        verified_evidence_id=evidence.id,
        source_key=source.source_key,
        promotion_state=promotion_state,
        policy_decision=assessment.decision,
        policy_reason=assessment.reason,
        conflict_key=conflict_key,
        canonical_conflict_id=conflict_id,
    )
