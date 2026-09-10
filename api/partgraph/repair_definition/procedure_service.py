"""Compatibility facade plus PartGraph MVP support-boundary enforcement."""

from collections.abc import Collection
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..knowledge import procedure_service as _service
from ..knowledge.models import ProcedureAction, RepairDefinition
from ..knowledge.schemas import RepairProcedureRead
from ..knowledge.support_boundaries import (
    ProcedureBoundaryAction,
    validate_computer_service_boundary,
)

REPAIR_PROCEDURE_NOT_AVAILABLE = _service.REPAIR_PROCEDURE_NOT_AVAILABLE
REPAIR_PROCEDURE_INTEGRITY_ERROR = _service.REPAIR_PROCEDURE_INTEGRITY_ERROR
REPAIR_GUIDANCE_PROFESSIONAL_REQUIRED = _service.REPAIR_GUIDANCE_PROFESSIONAL_REQUIRED
REPAIR_GUIDANCE_PROHIBITED = _service.REPAIR_GUIDANCE_PROHIBITED
_integrity_error = _service._integrity_error
_policy_error = _service._policy_error
_validate_dependency_graph = _service._validate_dependency_graph


async def _validate_support_boundary(
    session: AsyncSession,
    repair_definition_id: UUID,
) -> None:
    actions = list(
        await session.scalars(
            select(ProcedureAction)
            .where(ProcedureAction.repair_definition_id == repair_definition_id)
            .order_by(ProcedureAction.position, ProcedureAction.id)
        )
    )
    try:
        validate_computer_service_boundary(
            ProcedureBoundaryAction(
                action_key=action.action_key,
                position=action.position,
                skippable=action.skippable,
            )
            for action in actions
        )
    except ValueError as exc:
        raise _integrity_error(str(exc)) from exc


async def _procedure_for_definition(
    session: AsyncSession,
    *,
    definition: RepairDefinition,
    allowed_claim_states: Collection[str],
) -> RepairProcedureRead:
    result = await _service._procedure_for_definition(
        session,
        definition=definition,
        allowed_claim_states=allowed_claim_states,
    )
    await _validate_support_boundary(session, definition.id)
    return result


async def verified_procedure_plan(
    session: AsyncSession,
    *,
    vehicle_configuration_id: UUID,
    repair_key: str,
) -> RepairProcedureRead:
    result = await _service.verified_procedure_plan(
        session,
        vehicle_configuration_id=vehicle_configuration_id,
        repair_key=repair_key,
    )
    await _validate_support_boundary(session, result.repair_definition_id)
    return result


__all__ = [
    "REPAIR_PROCEDURE_NOT_AVAILABLE",
    "REPAIR_PROCEDURE_INTEGRITY_ERROR",
    "REPAIR_GUIDANCE_PROFESSIONAL_REQUIRED",
    "REPAIR_GUIDANCE_PROHIBITED",
    "_integrity_error",
    "_policy_error",
    "_validate_dependency_graph",
    "_procedure_for_definition",
    "verified_procedure_plan",
]
