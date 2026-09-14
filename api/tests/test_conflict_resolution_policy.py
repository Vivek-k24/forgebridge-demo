import unittest
from types import SimpleNamespace
from uuid import uuid4

from pydantic import ValidationError

from partgraph.errors import ErrorCode, PartGraphError
from partgraph.knowledge.conflict_resolution import (
    CanonicalConflictResolutionCreate,
    _selected_item_id,
)


class ConflictResolutionPolicyTests(unittest.TestCase):
    def test_selection_is_required_when_a_claim_wins(self) -> None:
        for resolution in ("accepted_evidence", "superseded", "duplicate"):
            with self.subTest(resolution=resolution):
                with self.assertRaises(ValidationError):
                    CanonicalConflictResolutionCreate(
                        resolution=resolution,
                        rationale="source-specific review selected the supported fact",
                    )

    def test_selection_is_forbidden_when_no_claim_wins(self) -> None:
        selected = uuid4()
        for resolution in ("insufficient_evidence", "not_applicable"):
            with self.subTest(resolution=resolution):
                with self.assertRaises(ValidationError):
                    CanonicalConflictResolutionCreate(
                        resolution=resolution,
                        selected_claim_id=selected,
                        rationale="no contender establishes canonical truth",
                    )

    def test_valid_resolution_normalizes_audit_rationale(self) -> None:
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

    def test_multiple_selected_items_are_rejected_as_corrupt_state(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
