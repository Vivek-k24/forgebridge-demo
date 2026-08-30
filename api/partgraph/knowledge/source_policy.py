from dataclasses import dataclass
from enum import StrEnum


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
    PART_FITMENT = "part_fitment"


class ClaimRisk(StrEnum):
    NORMAL = "normal"
    SAFETY_CRITICAL = "safety_critical"


class PromotionDecision(StrEnum):
    ELIGIBLE = "eligible"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    CANDIDATE_ONLY = "candidate_only"


@dataclass(frozen=True, slots=True)
class PromotionAssessment:
    decision: PromotionDecision
    reason: str


def assess_mechanical_claim(
    *,
    source_class: SourceClass,
    claim_domain: ClaimDomain,
    exact_applicability: bool,
    explicit_claim: bool,
    risk: ClaimRisk = ClaimRisk.NORMAL,
    has_conflict: bool = False,
) -> PromotionAssessment:
    """Evaluate whether evidence may establish canonical mechanical truth.

    Source authority is evaluated separately from parser/model confidence.
    Licensing and terms remain a separate source-instance gate before
    automation may ingest from a source.
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

    if source_class is SourceClass.GOVERNMENT:
        if claim_domain is ClaimDomain.VEHICLE_IDENTITY:
            return PromotionAssessment(
                PromotionDecision.ELIGIBLE,
                "government vehicle identity data is authoritative for identity evidence",
            )
        if claim_domain is ClaimDomain.SAFETY_CAMPAIGN:
            return PromotionAssessment(
                PromotionDecision.HUMAN_REVIEW_REQUIRED,
                "campaign metadata is authoritative but repair implications require review",
            )
        return PromotionAssessment(
            PromotionDecision.CANDIDATE_ONLY,
            "government identity/safety datasets do not establish general repair requirements",
        )

    if source_class in {SourceClass.OEM_SERVICE, SourceClass.LICENSED_OEM_DERIVED}:
        if risk is ClaimRisk.SAFETY_CRITICAL:
            return PromotionAssessment(
                PromotionDecision.HUMAN_REVIEW_REQUIRED,
                "safety-critical mechanical claims require human review initially",
            )
        return PromotionAssessment(
            PromotionDecision.ELIGIBLE,
            "explicit exact-applicability OEM service evidence is eligible for promotion",
        )

    if source_class is SourceClass.OEM_PARTS:
        if claim_domain is ClaimDomain.PART_FITMENT:
            return PromotionAssessment(
                PromotionDecision.ELIGIBLE,
                "explicit exact-applicability OEM parts evidence may establish part fitment",
            )
        return PromotionAssessment(
            PromotionDecision.CANDIDATE_ONLY,
            "a parts catalog does not establish repair procedure or tool requirements",
        )

    if source_class is SourceClass.INDUSTRY_STANDARD:
        return PromotionAssessment(
            PromotionDecision.CANDIDATE_ONLY,
            "industry standards normalize communication but do not supply application truth",
        )

    if source_class is SourceClass.RETAILER:
        return PromotionAssessment(
            PromotionDecision.CANDIDATE_ONLY,
            "retailer listings are procurement evidence, not canonical mechanical truth",
        )

    return PromotionAssessment(
        PromotionDecision.CANDIDATE_ONLY,
        "community evidence may support discovery but cannot auto-promote mechanical truth",
    )
