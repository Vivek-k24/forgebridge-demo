"""Compatibility imports for pre-restructure source-promotion policy."""

from ..knowledge.source_policy import (
    ClaimDomain,
    ClaimRisk,
    PromotionAssessment,
    PromotionDecision,
    SourceClass,
    assess_mechanical_claim,
)

__all__ = [
    "SourceClass",
    "ClaimDomain",
    "ClaimRisk",
    "PromotionDecision",
    "PromotionAssessment",
    "assess_mechanical_claim",
]
