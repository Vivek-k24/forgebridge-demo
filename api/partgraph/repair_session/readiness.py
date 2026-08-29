from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel
from sqlalchemy import select

from ..auth.dependencies import AuthSessionDep, CurrentUserDep
from ..errors import ErrorCode, ErrorEnvelope, PartGraphError
from ..repair_definition.models import RepairRequirementState, UserGarageInventoryItem
from ..repair_definition.service import bound_requirement_manifest
from ..user_vehicle.models import UserVehicle
from .models import RepairSession

ReadinessState = Literal["have", "missing", "ordered", "unavailable"]
ReadinessSource = Literal["session", "garage", "existing_vehicle", "default"]


class RepairReadinessItemRead(BaseModel):
    requirement_definition_id: UUID
    requirement_key: str
    category: str
    display_name: str
    required_quantity: Decimal | None
    unit: str | None
    necessity: str
    fulfillment_mode: str
    operation_keys: list[str]
    quantity_available: Decimal
    readiness_state: ReadinessState
    readiness_source: ReadinessSource
    procurement_reference: str | None = None
    notes: str | None = None


class RepairReadinessSummaryRead(BaseModel):
    total: int
    ready: int
    missing: int
    ordered: int
    unavailable: int
    blocked: int


class BoundRepairRead(BaseModel):
    repair_definition_id: UUID
    repair_key: str
    title: str
    version: int
    definition_status: Literal["verified", "superseded"]


class RepairReadinessRead(BaseModel):
    session_id: UUID
    binding_status: Literal["unbound", "bound"]
    repair: BoundRepairRead | None
    summary: RepairReadinessSummaryRead
    requirements: list[RepairReadinessItemRead]


router = APIRouter(
    prefix="/api/v1/repair-sessions",
    tags=["Repair Readiness"],
    responses={
        401: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope},
        500: {"model": ErrorEnvelope},
    },
)


def _empty_readiness(session_id: UUID) -> RepairReadinessRead:
    return RepairReadinessRead(
        session_id=session_id,
        binding_status="unbound",
        repair=None,
        summary=RepairReadinessSummaryRead(
            total=0,
            ready=0,
            missing=0,
            ordered=0,
            unavailable=0,
            blocked=0,
        ),
        requirements=[],
    )


def _garage_satisfies(
    *,
    required_quantity: Decimal | None,
    required_unit: str | None,
    garage: UserGarageInventoryItem,
) -> bool:
    if required_unit != garage.unit:
        return False
    if required_quantity is None:
        return garage.quantity_available > 0
    return garage.quantity_available >= required_quantity


def _default_item_state(
    *,
    fulfillment_mode: str,
    garage: UserGarageInventoryItem | None,
    required_quantity: Decimal | None,
    unit: str | None,
) -> tuple[ReadinessState, ReadinessSource, Decimal]:
    if fulfillment_mode in {"reuse_existing", "replace_if_damaged"}:
        return "have", "existing_vehicle", required_quantity or Decimal("1")
    if garage is not None and _garage_satisfies(
        required_quantity=required_quantity,
        required_unit=unit,
        garage=garage,
    ):
        return "have", "garage", garage.quantity_available
    return "missing", "default", garage.quantity_available if garage is not None else Decimal("0")


@router.get("/{session_id}/readiness", response_model=RepairReadinessRead)
async def repair_readiness(
    session_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
) -> RepairReadinessRead:
    repair_session = await db.scalar(
        select(RepairSession).where(
            RepairSession.id == session_id,
            RepairSession.user_id == user.id,
        )
    )
    if repair_session is None:
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_NOT_FOUND,
            message="Repair session not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if repair_session.repair_definition_id is None:
        return _empty_readiness(session_id)

    vehicle = await db.scalar(
        select(UserVehicle).where(
            UserVehicle.id == repair_session.user_vehicle_id,
            UserVehicle.user_id == user.id,
        )
    )
    if vehicle is None or vehicle.canonical_configuration_id is None:
        raise PartGraphError(
            code="REPAIR_DEFINITION_BINDING_INVALID",
            message="Bound repair session no longer has an exact canonical vehicle configuration.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    manifest = await bound_requirement_manifest(
        db,
        repair_definition_id=repair_session.repair_definition_id,
        vehicle_configuration_id=vehicle.canonical_configuration_id,
    )
    requirement_ids = [item.requirement_definition_id for item in manifest.requirements]

    state_rows = list(
        await db.scalars(
            select(RepairRequirementState).where(
                RepairRequirementState.user_id == user.id,
                RepairRequirementState.session_id == session_id,
                RepairRequirementState.requirement_definition_id.in_(requirement_ids),
            )
        )
    ) if requirement_ids else []
    states = {row.requirement_definition_id: row for row in state_rows}

    garage_rows = list(
        await db.scalars(
            select(UserGarageInventoryItem).where(
                UserGarageInventoryItem.user_id == user.id,
                UserGarageInventoryItem.requirement_definition_id.in_(requirement_ids),
            )
        )
    ) if requirement_ids else []
    garage = {row.requirement_definition_id: row for row in garage_rows}

    items: list[RepairReadinessItemRead] = []
    for requirement in manifest.requirements:
        state_row = states.get(requirement.requirement_definition_id)
        if state_row is not None:
            readiness_state: ReadinessState = state_row.readiness_state  # type: ignore[assignment]
            readiness_source: ReadinessSource = "session"
            quantity_available = state_row.quantity_available
            procurement_reference = state_row.procurement_reference
            notes = state_row.notes
        else:
            readiness_state, readiness_source, quantity_available = _default_item_state(
                fulfillment_mode=requirement.fulfillment_mode,
                garage=garage.get(requirement.requirement_definition_id),
                required_quantity=requirement.required_quantity,
                unit=requirement.unit,
            )
            procurement_reference = None
            notes = None

        items.append(
            RepairReadinessItemRead(
                requirement_definition_id=requirement.requirement_definition_id,
                requirement_key=requirement.requirement_key,
                category=requirement.category,
                display_name=requirement.display_name,
                required_quantity=requirement.required_quantity,
                unit=requirement.unit,
                necessity=requirement.necessity,
                fulfillment_mode=requirement.fulfillment_mode,
                operation_keys=requirement.operation_keys,
                quantity_available=quantity_available,
                readiness_state=readiness_state,
                readiness_source=readiness_source,
                procurement_reference=procurement_reference,
                notes=notes,
            )
        )

    ready = sum(item.readiness_state == "have" for item in items)
    missing = sum(item.readiness_state == "missing" for item in items)
    ordered = sum(item.readiness_state == "ordered" for item in items)
    unavailable = sum(item.readiness_state == "unavailable" for item in items)
    blocked = sum(
        item.necessity == "required" and item.readiness_state != "have"
        for item in items
    )

    return RepairReadinessRead(
        session_id=session_id,
        binding_status="bound",
        repair=BoundRepairRead(
            repair_definition_id=manifest.repair_definition_id,
            repair_key=manifest.repair_key,
            title=manifest.title,
            version=manifest.version,
            definition_status=manifest.definition_status,
        ),
        summary=RepairReadinessSummaryRead(
            total=len(items),
            ready=ready,
            missing=missing,
            ordered=ordered,
            unavailable=unavailable,
            blocked=blocked,
        ),
        requirements=items,
    )
