from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .provenance import SourceAuthorityPolicy


class SourceClass(StrEnum):
    GOVERNMENT = "government"
    OEM_SERVICE = "oem_service"
    LICENSED_OEM_DERIVED = "licensed_oem_derived"
    OEM_PARTS = "oem_parts"
    INDUSTRY_STANDARD = "industry_standard"
    RETAILER = "retailer"
    COMMUNITY = "community"


class ClaimDomain(StrEnum):
    VEHICLE_IDENTITY = "vehicle_identity"
    SAFETY_CAMPAIGN = "safety_campaign"
    REPAIR_REQUIREMENT = "repair_requirement"
    REPAIR_PROCEDURE = "repair_procedure"
    PART_FITMENT = "part_fitment"


class ClaimRisk(StrEnum):
    NORMAL = "normal"
    SAFETY_CRITICAL = "safety_critical"


class PromotionDecision(StrEnum):
    ELIGIBLE = "eligible"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    CANDIDATE_ONLY = "candidate_only"


CLAIM_CANONICAL_DOMAIN: dict[ClaimDomain, str | None] = {
    ClaimDomain.VEHICLE_IDENTITY: "vehicle_identity",
    ClaimDomain.SAFETY_CAMPAIGN: None,
    ClaimDomain.REPAIR_REQUIREMENT: "requirement",
    ClaimDomain.REPAIR_PROCEDURE: "procedure",
    ClaimDomain.PART_FITMENT: "fitment",
}


class AuthorityPolicyRecord(Protocol):
    claim_domain: str | None
    canonical_domain: str | None
    source_class: str
    risk_class: str
    authority_state: str
    requires_exact_applicability: bool
    minimum_evidence_count: int
    rationale: str


@dataclass(frozen=True, slots=True)
class PromotionAssessment:
    decision: PromotionDecision
    reason: str


async def load_source_authority_policy(
    db: AsyncSession,
    *,
    source_class: SourceClass,
    claim_domain: ClaimDomain,
    risk: ClaimRisk,
) -> SourceAuthorityPolicy | None:
    """Load the exact policy row governing one mechanical-claim authority scope."""

    return await db.scalar(
        select(SourceAuthorityPolicy).where(
            SourceAuthorityPolicy.claim_domain == claim_domain.value,
            SourceAuthorityPolicy.source_class == source_class.value,
            SourceAuthorityPolicy.risk_class == risk.value,
        )
    )


def assess_mechanical_claim(
    *,
    policy: AuthorityPolicyRecord | None,
    source_class: SourceClass,
    claim_domain: ClaimDomain,
    exact_applicability: bool,
    explicit_claim: bool,
    risk: ClaimRisk = ClaimRisk.NORMAL,
    evidence_count: int = 1,
    has_conflict: bool = False,
) -> PromotionAssessment:
    """Evaluate a claim using structural invariants plus canonical authority data.

    Exact applicability, explicit support, and unresolved conflicts are product
    invariants. Which source class is authoritative for a claim/risk scope is
    data in ``source_authority_policies`` rather than a Python source matrix.
    """

    if has_conflict:
        return PromotionAssessment(
            PromotionDecision.HUMAN_REVIEW_REQUIRED,
            "conflicting evidence must never overwrite canonical truth automatically",
        )

    if not exact_applicability:
        return PromotionAssessment(
            PromotionDecision.HUMAN_REVIEW_REQUIRED,
            "vehicle or repair applicability is not exact",
        )

    if not explicit_claim:
        return PromotionAssessment(
            PromotionDecision.CANDIDATE_ONLY,
            "mechanical truth cannot be promoted from unsupported inference",
        )

    if policy is None:
        return PromotionAssessment(
            PromotionDecision.CANDIDATE_ONLY,
            "no source authority policy is registered for this claim scope",
        )

    expected_domain = CLAIM_CANONICAL_DOMAIN[claim_domain]
    if (
        policy.claim_domain != claim_domain.value
        or policy.canonical_domain != expected_domain
        or policy.source_class != source_class.value
        or policy.risk_class != risk.value
    ):
        return PromotionAssessment(
            PromotionDecision.CANDIDATE_ONLY,
            "source authority policy scope is inconsistent with the mechanical claim",
        )

    if policy.requires_exact_applicability and not exact_applicability:
        return PromotionAssessment(
            PromotionDecision.HUMAN_REVIEW_REQUIRED,
            "source authority policy requires exact vehicle applicability",
        )

    if evidence_count < policy.minimum_evidence_count:
        return PromotionAssessment(
            PromotionDecision.HUMAN_REVIEW_REQUIRED,
            "source authority policy requires additional independent evidence",
        )

    if policy.authority_state == "accepted":
        decision = PromotionDecision.ELIGIBLE
    elif policy.authority_state == "conditional":
        decision = PromotionDecision.HUMAN_REVIEW_REQUIRED
    else:
        decision = PromotionDecision.CANDIDATE_ONLY
    return PromotionAssessment(decision, policy.rationale)
