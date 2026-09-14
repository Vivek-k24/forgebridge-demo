import unittest
from types import SimpleNamespace
from uuid import UUID, uuid4

from pydantic import ValidationError

from partgraph.errors import ErrorCode, PartGraphError
from partgraph.knowledge.repair_materialization_contract import (
    IDEMPOTENCY_PATTERN,
    RepairDefinitionMaterializationCreate,
    assert_payload_coverage,
    request_sha256,
)
from partgraph.knowledge.support_boundaries import COMPUTER_SERVICE_BOUNDARY_ACTION_KEY

CONFIGURATION_ID = UUID("22222222-2222-4222-8222-222222222222")
CLAIM_ID = UUID("33333333-3333-4333-8333-333333333333")


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
        "supporting_claim_ids": [CLAIM_ID],
    }


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


def _request(**overrides: object) -> RepairDefinitionMaterializationCreate:
    value: dict[str, object] = {
        "vehicle_configuration_id": CONFIGURATION_ID,
        "repair_key": "cover.remove",
        "title": "Remove cover",
        "capability_policy_key": "diy_supported",
        "operations": [
            {"operation_key": "remove-cover", "label": "Remove cover", "position": 0}
        ],
        "requirements": [_requirement()],
        "actions": [_action()],
    }
    value.update(overrides)
    return RepairDefinitionMaterializationCreate.model_validate(value)


class RepairMaterializationPolicyTests(unittest.TestCase):
    def test_request_hash_is_deterministic(self) -> None:
        request = _request()
        self.assertEqual(request_sha256(request), request_sha256(request))
        self.assertEqual(len(request_sha256(request)), 64)

    def test_unreferenced_operation_is_rejected(self) -> None:
        requirement = _requirement()
        requirement["timing"] = "whole_repair"
        requirement["operation_key"] = None
        with self.assertRaises(ValidationError):
            _request(requirements=[requirement])

    def test_dependency_must_precede_dependent_action(self) -> None:
        first = _action(action_key="first", position=1, requirement_use_keys=[])
        second = _action(
            action_key="second",
            position=0,
            prerequisite_action_keys=["first"],
            requirement_use_keys=["socket-use"],
        )
        with self.assertRaises(ValidationError):
            _request(actions=[first, second])

    def test_computer_service_boundary_must_be_terminal_and_not_skippable(self) -> None:
        boundary = _action(
            action_key=COMPUTER_SERVICE_BOUNDARY_ACTION_KEY,
            position=0,
            requirement_use_keys=[],
        )
        physical = _action(action_key="physical-step", position=1)
        with self.assertRaises(ValidationError):
            _request(actions=[boundary, physical])

    def test_claims_may_collectively_cover_one_materialized_fact(self) -> None:
        claims = [
            SimpleNamespace(claim_payload={"requirement_key": "tool.socket-10mm"}),
            SimpleNamespace(claim_payload={"category": "tool", "quantity": "1.000"}),
        ]
        assert_payload_coverage(  # type: ignore[arg-type]
            claims,
            {
                "requirement_key": "tool.socket-10mm",
                "category": "tool",
                "quantity": 1,
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

    def test_idempotency_key_contract_is_bounded(self) -> None:
        self.assertIsNotNone(IDEMPOTENCY_PATTERN.fullmatch("repair:publish:001"))
        self.assertIsNone(IDEMPOTENCY_PATTERN.fullmatch("short"))
        self.assertIsNone(IDEMPOTENCY_PATTERN.fullmatch("contains space"))


if __name__ == "__main__":
    unittest.main()
