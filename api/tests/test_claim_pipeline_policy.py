import unittest
from decimal import Decimal
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
from partgraph.knowledge.repair_materialization_contract import (
    IDEMPOTENCY_PATTERN,
    RepairDefinitionMaterializationCreate,
    assert_payload_coverage,
    request_sha256,
)
from partgraph.knowledge.source_policy import (
    ClaimDomain,
    ClaimRisk,
    PromotionDecision,
    SourceClass,
    assess_mechanical_claim,
)
from partgraph.knowledge.support_boundaries import COMPUTER_SERVICE_BOUNDARY_ACTION_KEY

CONFIGURATION_ID = UUID("11111111-1111-4111-8111-111111111111")
MATERIALIZATION_CONFIGURATION_ID = UUID("22222222-2222-4222-8222-222222222222")
MATERIALIZATION_CLAIM_ID = UUID("33333333-3333-4333-8333-333333333333")


class ClaimPipelinePolicyTests(unittest.TestCase):
    @staticmethod
    def _policy(
        *,
        source_class: SourceClass,
        claim_domain: ClaimDomain,
        risk: ClaimRisk = ClaimRisk.NORMAL,
        authority_state: str,
    ) -> SimpleNamespace:
        canonical_domains = {
            ClaimDomain.VEHICLE_IDENTITY: "vehicle_identity",
            ClaimDomain.SAFETY_CAMPAIGN: None,
            ClaimDomain.REPAIR_REQUIREMENT: "requirement",
            ClaimDomain.REPAIR_PROCEDURE: "procedure",
            ClaimDomain.PART_FITMENT: "fitment",
        }
        return SimpleNamespace(
            claim_domain=claim_domain.value,
            canonical_domain=canonical_domains[claim_domain],
            source_class=source_class.value,
            risk_class=risk.value,
            authority_state=authority_state,
            requires_exact_applicability=True,
            minimum_evidence_count=1,
            rationale="fixture authority policy",
        )

    def test_accepted_policy_makes_exact_explicit_claim_eligible(self) -> None:
        policy = self._policy(
            source_class=SourceClass.OEM_SERVICE,
            claim_domain=ClaimDomain.REPAIR_PROCEDURE,
            authority_state="accepted",
        )
        assessment = assess_mechanical_claim(
            policy=policy,
            source_class=SourceClass.OEM_SERVICE,
            claim_domain=ClaimDomain.REPAIR_PROCEDURE,
            exact_applicability=True,
            explicit_claim=True,
        )
        self.assertEqual(assessment.decision, PromotionDecision.ELIGIBLE)

    def test_rejected_policy_remains_candidate_only(self) -> None:
        policy = self._policy(
            source_class=SourceClass.OEM_PARTS,
            claim_domain=ClaimDomain.REPAIR_PROCEDURE,
            authority_state="rejected",
        )
        assessment = assess_mechanical_claim(
            policy=policy,
            source_class=SourceClass.OEM_PARTS,
            claim_domain=ClaimDomain.REPAIR_PROCEDURE,
            exact_applicability=True,
            explicit_claim=True,
        )
        self.assertEqual(assessment.decision, PromotionDecision.CANDIDATE_ONLY)

    def test_missing_policy_fails_closed(self) -> None:
        assessment = assess_mechanical_claim(
            policy=None,
            source_class=SourceClass.RETAILER,
            claim_domain=ClaimDomain.PART_FITMENT,
            exact_applicability=True,
            explicit_claim=True,
        )
        self.assertEqual(assessment.decision, PromotionDecision.CANDIDATE_ONLY)

    def test_conflict_never_promotes_directly(self) -> None:
        policy = self._policy(
            source_class=SourceClass.OEM_SERVICE,
            claim_domain=ClaimDomain.REPAIR_REQUIREMENT,
            authority_state="accepted",
        )
        assessment = assess_mechanical_claim(
            policy=policy,
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

    def test_curator_review_satisfies_conditional_policy_gate(self) -> None:
        policy = self._policy(
            source_class=SourceClass.OEM_SERVICE,
            claim_domain=ClaimDomain.REPAIR_REQUIREMENT,
            risk=ClaimRisk.SAFETY_CRITICAL,
            authority_state="conditional",
        )
        assessment = assess_mechanical_claim(
            policy=policy,
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

    def test_policy_scope_mismatch_fails_closed(self) -> None:
        policy = self._policy(
            source_class=SourceClass.OEM_SERVICE,
            claim_domain=ClaimDomain.REPAIR_REQUIREMENT,
            authority_state="accepted",
        )
        policy.canonical_domain = "procedure"
        assessment = assess_mechanical_claim(
            policy=policy,
            source_class=SourceClass.OEM_SERVICE,
            claim_domain=ClaimDomain.REPAIR_REQUIREMENT,
            exact_applicability=True,
            explicit_claim=True,
        )
        self.assertEqual(assessment.decision, PromotionDecision.CANDIDATE_ONLY)

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
        self.assertEqual(request.rationale, "exact OEM evidence supports this contender")

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


class RepairMaterializationPolicyTests(unittest.TestCase):
    @staticmethod
    def _requirement() -> dict[str, object]:
        return {
            "use_key": "socket-use",
            "requirement_key": "tool.socket-10mm",
            "category": "tool",
            "display_name": "10 mm socket",
            "necessity": "required",
            "fulfillment_mode": "reusable",
            "timing": "operation",
            "operation_key": "remove-cover",
            "supporting_claim_ids": [MATERIALIZATION_CLAIM_ID],
        }

    @staticmethod
    def _action(**overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "action_key": "remove-cover",
            "title": "Remove cover",
            "instruction": "Remove the cover fasteners.",
            "position": 0,
            "skippable": False,
            "requirement_use_keys": ["socket-use"],
            "supporting_claim_ids": [uuid4()],
        }
        value.update(overrides)
        return value

    def _request(self, **overrides: object) -> RepairDefinitionMaterializationCreate:
        value: dict[str, object] = {
            "vehicle_configuration_id": MATERIALIZATION_CONFIGURATION_ID,
            "repair_key": "cover.remove",
            "title": "Remove cover",
            "capability_policy_key": "diy_supported",
            "operations": [
                {
                    "operation_key": "remove-cover",
                    "label": "Remove cover",
                    "position": 0,
                }
            ],
            "requirements": [self._requirement()],
            "actions": [self._action()],
        }
        value.update(overrides)
        return RepairDefinitionMaterializationCreate.model_validate(value)

    def test_materialization_request_hash_is_deterministic(self) -> None:
        request = self._request()
        self.assertEqual(request_sha256(request), request_sha256(request))
        self.assertEqual(len(request_sha256(request)), 64)

    def test_unreferenced_operation_is_rejected(self) -> None:
        requirement = self._requirement()
        requirement["timing"] = "whole_repair"
        requirement["operation_key"] = None
        with self.assertRaises(ValidationError):
            self._request(requirements=[requirement])

    def test_dependency_must_precede_dependent_action(self) -> None:
        first = self._action(action_key="first", position=1, requirement_use_keys=[])
        second = self._action(
            action_key="second",
            position=0,
            prerequisite_action_keys=["first"],
            requirement_use_keys=["socket-use"],
        )
        with self.assertRaises(ValidationError):
            self._request(actions=[first, second])

    def test_computer_service_boundary_must_be_terminal(self) -> None:
        boundary = self._action(
            action_key=COMPUTER_SERVICE_BOUNDARY_ACTION_KEY,
            position=0,
            requirement_use_keys=[],
        )
        physical = self._action(action_key="physical-step", position=1)
        with self.assertRaises(ValidationError):
            self._request(actions=[boundary, physical])

    def test_claims_may_collectively_cover_materialized_fact(self) -> None:
        claims = [
            SimpleNamespace(claim_payload={"requirement_key": "tool.socket-10mm"}),
            SimpleNamespace(claim_payload={"category": "tool", "quantity": "1.000"}),
        ]
        assert_payload_coverage(  # type: ignore[arg-type]
            claims,
            {
                "requirement_key": "tool.socket-10mm",
                "category": "tool",
                "quantity": Decimal("1"),
            },
            fact_label="requirement[socket-use]",
        )

    def test_conflicting_supporting_payload_is_rejected(self) -> None:
        claims = [
            SimpleNamespace(claim_payload={"category": "tool"}),
            SimpleNamespace(claim_payload={"category": "fluid"}),
        ]
        with self.assertRaises(PartGraphError) as context:
            assert_payload_coverage(  # type: ignore[arg-type]
                claims,
                {"category": "tool"},
                fact_label="requirement[socket-use]",
            )
        self.assertEqual(
            context.exception.code,
            ErrorCode.KNOWLEDGE_MATERIALIZATION_INVALID,
        )

    def test_materialization_idempotency_key_contract_is_bounded(self) -> None:
        self.assertIsNotNone(IDEMPOTENCY_PATTERN.fullmatch("repair:publish:001"))
        self.assertIsNone(IDEMPOTENCY_PATTERN.fullmatch("short"))
        self.assertIsNone(IDEMPOTENCY_PATTERN.fullmatch("contains space"))


if __name__ == "__main__":
    unittest.main()
