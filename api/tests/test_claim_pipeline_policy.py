import unittest
from types import SimpleNamespace
from uuid import UUID, uuid4

from pydantic import ValidationError

from partgraph.errors import ErrorCode, PartGraphError
from partgraph.knowledge.claim_publication import (
    MechanicalClaimPublicationRead,
    VerifiedMechanicalClaimSpec,
    _conflict_key,
    _promotion_state,
)
from partgraph.knowledge.conflict_resolution import (
    CanonicalConflictResolutionCreate,
    _selected_item_id,
)
from partgraph.knowledge.source_policy import (
    ClaimDomain,
    ClaimRisk,
    PromotionDecision,
    SourceClass,
    assess_mechanical_claim,
)

CONFIGURATION_ID = UUID("11111111-1111-4111-8111-111111111111")


class ClaimPipelinePolicyTests(unittest.TestCase):
    def test_oem_service_exact_explicit_procedure_is_eligible(self) -> None:
        assessment = assess_mechanical_claim(
            source_class=SourceClass.OEM_SERVICE,
            claim_domain=ClaimDomain.REPAIR_PROCEDURE,
            exact_applicability=True,
            explicit_claim=True,
        )
        self.assertEqual(assessment.decision, PromotionDecision.ELIGIBLE)

    def test_oem_parts_does_not_establish_repair_procedure(self) -> None:
        assessment = assess_mechanical_claim(
            source_class=SourceClass.OEM_PARTS,
            claim_domain=ClaimDomain.REPAIR_PROCEDURE,
            exact_applicability=True,
            explicit_claim=True,
        )
        self.assertEqual(assessment.decision, PromotionDecision.CANDIDATE_ONLY)

    def test_retailer_fitment_remains_candidate_only(self) -> None:
        assessment = assess_mechanical_claim(
            source_class=SourceClass.RETAILER,
            claim_domain=ClaimDomain.PART_FITMENT,
            exact_applicability=True,
            explicit_claim=True,
        )
        self.assertEqual(assessment.decision, PromotionDecision.CANDIDATE_ONLY)

    def test_conflict_never_promotes_directly(self) -> None:
        assessment = assess_mechanical_claim(
            source_class=SourceClass.OEM_SERVICE,
            claim_domain=ClaimDomain.REPAIR_REQUIREMENT,
            exact_applicability=True,
            explicit_claim=True,
            has_conflict=True,
        )
        self.assertEqual(
            _promotion_state(
                decision=assessment.decision,
                exact_applicability=True,
                explicit_claim=True,
                has_conflict=True,
            ),
            "conflict",
        )

    def test_curator_review_satisfies_safety_critical_human_review_gate(self) -> None:
        assessment = assess_mechanical_claim(
            source_class=SourceClass.OEM_SERVICE,
            claim_domain=ClaimDomain.REPAIR_REQUIREMENT,
            exact_applicability=True,
            explicit_claim=True,
            risk=ClaimRisk.SAFETY_CRITICAL,
        )
        self.assertEqual(assessment.decision, PromotionDecision.HUMAN_REVIEW_REQUIRED)
        self.assertEqual(
            _promotion_state(
                decision=assessment.decision,
                exact_applicability=True,
                explicit_claim=True,
                has_conflict=False,
            ),
            "verified",
        )

    def test_non_exact_or_inferred_claim_cannot_become_verified(self) -> None:
        self.assertEqual(
            _promotion_state(
                decision=PromotionDecision.HUMAN_REVIEW_REQUIRED,
                exact_applicability=False,
                explicit_claim=True,
                has_conflict=False,
            ),
            "needs_review",
        )
        self.assertEqual(
            _promotion_state(
                decision=PromotionDecision.CANDIDATE_ONLY,
                exact_applicability=True,
                explicit_claim=False,
                has_conflict=False,
            ),
            "needs_review",
        )

    def test_conflict_key_is_deterministic_for_exact_scope(self) -> None:
        spec = VerifiedMechanicalClaimSpec(
            claim_domain=ClaimDomain.REPAIR_REQUIREMENT,
            normalized_key=" requirement.coolant ",
            claim_payload={"requirement_key": "fluid.coolant"},
            explicit_claim=True,
            exact_applicability=True,
            vehicle_configuration_id=CONFIGURATION_ID,
            repair_key="coolant.replace",
        )
        first = _conflict_key(spec)
        second = _conflict_key(spec)
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("mechanical:"))
        self.assertLessEqual(len(first), 128)

    def test_conflict_resolution_requires_selection_when_a_claim_wins(self) -> None:
        for resolution in ("accepted_evidence", "superseded", "duplicate"):
            with self.subTest(resolution=resolution):
                with self.assertRaises(ValidationError):
                    CanonicalConflictResolutionCreate(
                        resolution=resolution,
                        rationale="source-specific review selected the supported fact",
                    )

    def test_conflict_resolution_forbids_selection_when_no_claim_wins(self) -> None:
        selected = uuid4()
        for resolution in ("insufficient_evidence", "not_applicable"):
            with self.subTest(resolution=resolution):
                with self.assertRaises(ValidationError):
                    CanonicalConflictResolutionCreate(
                        resolution=resolution,
                        selected_claim_id=selected,
                        rationale="no contender establishes canonical truth",
                    )

    def test_conflict_resolution_normalizes_audit_rationale(self) -> None:
        selected = uuid4()
        request = CanonicalConflictResolutionCreate(
            resolution="accepted_evidence",
            selected_claim_id=selected,
            rationale="  exact   OEM evidence   supports this contender  ",
        )
        self.assertEqual(request.selected_claim_id, selected)
        self.assertEqual(
            request.rationale,
            "exact OEM evidence supports this contender",
        )

    def test_multiple_selected_conflict_items_are_rejected(self) -> None:
        items = [
            SimpleNamespace(disposition="selected", mechanical_claim_id=uuid4()),
            SimpleNamespace(disposition="selected", mechanical_claim_id=uuid4()),
        ]
        with self.assertRaises(PartGraphError) as context:
            _selected_item_id(items)  # type: ignore[arg-type]
        self.assertEqual(
            context.exception.code,
            ErrorCode.KNOWLEDGE_CONFLICT_RESOLUTION_INVALID,
        )

    def test_publication_response_accepts_final_resolution_states(self) -> None:
        for promotion_state in ("rejected", "superseded"):
            with self.subTest(promotion_state=promotion_state):
                response = MechanicalClaimPublicationRead(
                    mechanical_claim_id=uuid4(),
                    verified_evidence_id=uuid4(),
                    source_key="fixture-source",
                    promotion_state=promotion_state,
                    policy_decision=PromotionDecision.ELIGIBLE,
                    policy_reason="previously reviewed evidence",
                    conflict_key="mechanical:" + "a" * 64,
                    idempotent=True,
                )
                self.assertEqual(response.promotion_state, promotion_state)


if __name__ == "__main__":
    unittest.main()
