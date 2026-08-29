import pytest

from partgraph.catalog.source_policy import (
    ClaimDomain,
    ClaimRisk,
    PromotionDecision,
    SourceClass,
    assess_mechanical_claim,
)


@pytest.mark.parametrize(
    ("source_class", "claim_domain", "expected"),
    [
        (SourceClass.GOVERNMENT, ClaimDomain.VEHICLE_IDENTITY, PromotionDecision.ELIGIBLE),
        (SourceClass.OEM_SERVICE, ClaimDomain.REPAIR_REQUIREMENT, PromotionDecision.ELIGIBLE),
        (
            SourceClass.LICENSED_OEM_DERIVED,
            ClaimDomain.REPAIR_REQUIREMENT,
            PromotionDecision.ELIGIBLE,
        ),
        (SourceClass.OEM_PARTS, ClaimDomain.PART_FITMENT, PromotionDecision.ELIGIBLE),
        (
            SourceClass.OEM_PARTS,
            ClaimDomain.REPAIR_REQUIREMENT,
            PromotionDecision.CANDIDATE_ONLY,
        ),
        (
            SourceClass.INDUSTRY_STANDARD,
            ClaimDomain.PART_FITMENT,
            PromotionDecision.CANDIDATE_ONLY,
        ),
        (SourceClass.RETAILER, ClaimDomain.PART_FITMENT, PromotionDecision.CANDIDATE_ONLY),
        (
            SourceClass.COMMUNITY,
            ClaimDomain.REPAIR_REQUIREMENT,
            PromotionDecision.CANDIDATE_ONLY,
        ),
    ],
)
def test_source_authority_is_deterministic(
    source_class: SourceClass,
    claim_domain: ClaimDomain,
    expected: PromotionDecision,
) -> None:
    result = assess_mechanical_claim(
        source_class=source_class,
        claim_domain=claim_domain,
        exact_applicability=True,
        explicit_claim=True,
    )
    assert result.decision is expected


def test_parser_confidence_cannot_turn_inference_into_truth() -> None:
    result = assess_mechanical_claim(
        source_class=SourceClass.OEM_SERVICE,
        claim_domain=ClaimDomain.REPAIR_REQUIREMENT,
        exact_applicability=True,
        explicit_claim=False,
    )
    assert result.decision is PromotionDecision.CANDIDATE_ONLY
    assert "inference" in result.reason


def test_ambiguous_vehicle_applicability_requires_review() -> None:
    result = assess_mechanical_claim(
        source_class=SourceClass.OEM_SERVICE,
        claim_domain=ClaimDomain.REPAIR_REQUIREMENT,
        exact_applicability=False,
        explicit_claim=True,
    )
    assert result.decision is PromotionDecision.HUMAN_REVIEW_REQUIRED


def test_conflicting_oem_evidence_requires_review() -> None:
    result = assess_mechanical_claim(
        source_class=SourceClass.OEM_SERVICE,
        claim_domain=ClaimDomain.REPAIR_REQUIREMENT,
        exact_applicability=True,
        explicit_claim=True,
        has_conflict=True,
    )
    assert result.decision is PromotionDecision.HUMAN_REVIEW_REQUIRED
    assert "conflicting" in result.reason


def test_safety_critical_oem_claim_requires_human_review_initially() -> None:
    result = assess_mechanical_claim(
        source_class=SourceClass.OEM_SERVICE,
        claim_domain=ClaimDomain.REPAIR_REQUIREMENT,
        exact_applicability=True,
        explicit_claim=True,
        risk=ClaimRisk.SAFETY_CRITICAL,
    )
    assert result.decision is PromotionDecision.HUMAN_REVIEW_REQUIRED


def test_government_safety_campaign_is_not_repair_instruction() -> None:
    result = assess_mechanical_claim(
        source_class=SourceClass.GOVERNMENT,
        claim_domain=ClaimDomain.SAFETY_CAMPAIGN,
        exact_applicability=True,
        explicit_claim=True,
    )
    assert result.decision is PromotionDecision.HUMAN_REVIEW_REQUIRED


def test_retailer_can_never_auto_promote_mechanical_fitment() -> None:
    result = assess_mechanical_claim(
        source_class=SourceClass.RETAILER,
        claim_domain=ClaimDomain.PART_FITMENT,
        exact_applicability=True,
        explicit_claim=True,
    )
    assert result.decision is PromotionDecision.CANDIDATE_ONLY
    assert "procurement" in result.reason
