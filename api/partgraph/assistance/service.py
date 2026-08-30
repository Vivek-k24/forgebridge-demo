from ..repair_experience.guidance import RepairGuidanceRead
from .schemas import (
    AssistanceActionReference,
    AssistanceExplanationRead,
    AssistanceInventoryBlocker,
)


def explain_guidance(guidance: RepairGuidanceRead) -> AssistanceExplanationRead:
    """Explain existing verified guidance without generating new mechanical truth."""
    action = guidance.current_action

    if guidance.procedure_complete:
        return AssistanceExplanationRead(
            session_id=guidance.session_id,
            repair_definition_id=guidance.repair_definition_id,
            repair_key=guidance.repair_key,
            version=guidance.version,
            guidance_status=guidance.status,
            reason_code="verified_procedure_complete",
            headline="The verified procedure is complete.",
            explanation=(
                "Every action in this version-pinned verified procedure is recorded as "
                "completed or explicitly skippable-and-skipped. PartGraph has no further "
                "verified action to advance to."
            ),
            current_action=None,
            inventory_blockers=[],
        )

    assert action is not None
    action_reference = AssistanceActionReference(
        action_id=action.action_id,
        action_key=action.action_key,
        title=action.title,
        dependency_action_keys=action.dependency_action_keys,
        supporting_claim_ids=action.supporting_claim_ids,
    )
    blockers = [
        AssistanceInventoryBlocker(
            requirement_definition_id=item.requirement_definition_id,
            requirement_key=item.requirement_key,
            display_name=item.display_name,
            readiness_state=item.readiness_state,
            required_quantity=item.required_quantity,
            unit=item.unit,
        )
        for item in action.inventory_blockers
    ]

    if guidance.status == "inventory_blocked":
        names = ", ".join(item.display_name for item in blockers)
        return AssistanceExplanationRead(
            session_id=guidance.session_id,
            repair_definition_id=guidance.repair_definition_id,
            repair_key=guidance.repair_key,
            version=guidance.version,
            guidance_status=guidance.status,
            reason_code="current_action_inventory_blocked",
            headline="This is the next verified action, but Inventory is blocking it.",
            explanation=(
                f"The verified dependencies for {action.title} are satisfied, but required "
                f"Inventory is not marked Have: {names}. PartGraph will not allow this "
                "action to complete until those required items are resolved."
            ),
            current_action=action_reference,
            inventory_blockers=blockers,
        )

    if guidance.status == "action_blocked":
        return AssistanceExplanationRead(
            session_id=guidance.session_id,
            repair_definition_id=guidance.repair_definition_id,
            repair_key=guidance.repair_key,
            version=guidance.version,
            guidance_status=guidance.status,
            reason_code="current_action_physically_blocked",
            headline="PartGraph is holding the repair at this action.",
            explanation=(
                f"{action.title} is recorded as blocked. PartGraph keeps the same verified "
                "action current instead of silently skipping forward. Resolve the recorded "
                "problem before advancing."
            ),
            current_action=action_reference,
            inventory_blockers=blockers,
        )

    prerequisite_text = (
        "Its verified prerequisites are already complete or explicitly skipped, and its "
        "required Inventory is ready."
        if action.dependency_action_keys
        else "It is the first unresolved verified action whose required Inventory is ready."
    )
    return AssistanceExplanationRead(
        session_id=guidance.session_id,
        repair_definition_id=guidance.repair_definition_id,
        repair_key=guidance.repair_key,
        version=guidance.version,
        guidance_status=guidance.status,
        reason_code="next_verified_action",
        headline="This is the next action supported by the verified repair state.",
        explanation=(
            f"PartGraph selected {action.title} from the version-pinned verified procedure. "
            f"{prerequisite_text} No AI model was needed to choose or explain this action."
        ),
        current_action=action_reference,
        inventory_blockers=[],
    )
