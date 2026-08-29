import hashlib
import json
import re
from decimal import Decimal
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from ..auth.dependencies import AuthSessionDep, CurrentUserDep, require_csrf
from ..errors import ErrorCode, ErrorEnvelope, PartGraphError
from ..repair_definition.models import RepairRequirementState, UserGarageInventoryItem
from ..repair_definition.schemas import RepairDefinitionManifestRead, RequirementManifestItemRead
from ..repair_definition.service import bound_requirement_manifest
from ..user_vehicle.models import UserVehicle
from .models import RepairSession, RepairSessionEvent
from .service import append_domain_event, prepare_domain_mutation

ReadinessState = Literal["have", "missing", "ordered", "unavailable"]
ReadinessSource = Literal["session", "garage", "existing_vehicle", "default"]
DEVICE_HEADER = "X-PartGraph-Device-ID"
IDEMPOTENCY_HEADER = "Idempotency-Key"
IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
REUSABLE_GARAGE_CATEGORIES = {"tool", "equipment", "workspace"}
REPAIR_READINESS_UNBOUND = "REPAIR_READINESS_UNBOUND"
REPAIR_READINESS_REQUIREMENT_NOT_FOUND = "REPAIR_READINESS_REQUIREMENT_NOT_FOUND"


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


class RepairReadinessUpdate(BaseModel):
    readiness_state: ReadinessState
    quantity_available: Decimal | None = Field(default=None, ge=0)
    procurement_reference: str | None = Field(default=None, max_length=240)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("procurement_reference", "notes")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None


router = APIRouter(
    prefix="/api/v1/repair-sessions",
    tags=["Repair Readiness"],
    responses={
        401: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope},
        409: {"model": ErrorEnvelope},
        422: {"model": ErrorEnvelope},
        500: {"model": ErrorEnvelope},
    },
)
CsrfDep = Depends(require_csrf)


def _fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _assert_replay(event: RepairSessionEvent, fingerprint: str) -> None:
    if event.payload.get("request_fingerprint") != fingerprint:
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_IDEMPOTENCY_CONFLICT,
            message="Idempotency key was already used with different readiness data.",
            status_code=status.HTTP_409_CONFLICT,
        )


def _parse_device_id(value: str | None) -> UUID:
    if value is None:
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_DEVICE_ID_INVALID,
            message=f"{DEVICE_HEADER} is required for repair-session editing.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    try:
        return UUID(value)
    except ValueError as exc:
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_DEVICE_ID_INVALID,
            message=f"{DEVICE_HEADER} must be a UUID.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        ) from exc


def _parse_idempotency_key(value: str | None) -> str:
    if value is None or IDEMPOTENCY_PATTERN.fullmatch(value) is None:
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_IDEMPOTENCY_INVALID,
            message=(
                f"{IDEMPOTENCY_HEADER} must be 8-64 letters, digits, underscores, or hyphens."
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return value


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


async def _bound_manifest(
    db: AuthSessionDep,
    *,
    user_id: UUID,
    repair_session: RepairSession,
) -> RepairDefinitionManifestRead:
    if repair_session.repair_definition_id is None:
        raise PartGraphError(
            code=REPAIR_READINESS_UNBOUND,
            message="Bind an exact verified repair definition before reconciling readiness.",
            status_code=status.HTTP_409_CONFLICT,
        )
    vehicle = await db.scalar(
        select(UserVehicle).where(
            UserVehicle.id == repair_session.user_vehicle_id,
            UserVehicle.user_id == user_id,
        )
    )
    if vehicle is None or vehicle.canonical_configuration_id is None:
        raise PartGraphError(
            code="REPAIR_DEFINITION_BINDING_INVALID",
            message="Bound repair session no longer has an exact canonical vehicle configuration.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return await bound_requirement_manifest(
        db,
        repair_definition_id=repair_session.repair_definition_id,
        vehicle_configuration_id=vehicle.canonical_configuration_id,
    )


async def _readiness_view(
    db: AuthSessionDep,
    *,
    user_id: UUID,
    repair_session: RepairSession,
) -> RepairReadinessRead:
    if repair_session.repair_definition_id is None:
        return _empty_readiness(repair_session.id)

    manifest = await _bound_manifest(db, user_id=user_id, repair_session=repair_session)
    requirement_ids = [item.requirement_definition_id for item in manifest.requirements]

    state_rows = (
        list(
            await db.scalars(
                select(RepairRequirementState).where(
                    RepairRequirementState.user_id == user_id,
                    RepairRequirementState.session_id == repair_session.id,
                    RepairRequirementState.requirement_definition_id.in_(requirement_ids),
                )
            )
        )
        if requirement_ids
        else []
    )
    states = {row.requirement_definition_id: row for row in state_rows}

    garage_rows = (
        list(
            await db.scalars(
                select(UserGarageInventoryItem).where(
                    UserGarageInventoryItem.user_id == user_id,
                    UserGarageInventoryItem.requirement_definition_id.in_(requirement_ids),
                )
            )
        )
        if requirement_ids
        else []
    )
    garage = {row.requirement_definition_id: row for row in garage_rows}

    items: list[RepairReadinessItemRead] = []
    for requirement in manifest.requirements:
        state_row = states.get(requirement.requirement_definition_id)
        if state_row is not None:
            readiness_state = cast(ReadinessState, state_row.readiness_state)
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
        session_id=repair_session.id,
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


async def _target_requirement(
    manifest: RepairDefinitionManifestRead,
    requirement_definition_id: UUID,
) -> RequirementManifestItemRead:
    target = next(
        (
            item
            for item in manifest.requirements
            if item.requirement_definition_id == requirement_definition_id
        ),
        None,
    )
    if target is None:
        raise PartGraphError(
            code=REPAIR_READINESS_REQUIREMENT_NOT_FOUND,
            message="Requirement is not part of this repair session's verified manifest.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return target


def _resolved_quantity(
    target: RequirementManifestItemRead,
    payload: RepairReadinessUpdate,
) -> Decimal:
    if payload.quantity_available is not None:
        quantity = payload.quantity_available
    elif payload.readiness_state == "have":
        quantity = target.required_quantity or Decimal("1")
    else:
        quantity = Decimal("0")

    if (
        payload.readiness_state == "have"
        and target.required_quantity is not None
        and quantity < target.required_quantity
    ):
        raise PartGraphError(
            code=ErrorCode.REQUEST_VALIDATION_FAILED,
            message="Available quantity is below the verified required quantity.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    if payload.readiness_state == "have" and quantity <= 0:
        raise PartGraphError(
            code=ErrorCode.REQUEST_VALIDATION_FAILED,
            message="Have-it readiness requires a positive available quantity.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return quantity


async def _remember_reusable_requirement(
    db: AuthSessionDep,
    *,
    user_id: UUID,
    target: RequirementManifestItemRead,
    quantity_available: Decimal,
) -> bool:
    if target.fulfillment_mode != "reusable" or target.category not in REUSABLE_GARAGE_CATEGORIES:
        return False

    garage = await db.scalar(
        select(UserGarageInventoryItem)
        .where(
            UserGarageInventoryItem.user_id == user_id,
            UserGarageInventoryItem.requirement_definition_id == target.requirement_definition_id,
        )
        .with_for_update()
    )
    if garage is None:
        garage = UserGarageInventoryItem(
            user_id=user_id,
            requirement_definition_id=target.requirement_definition_id,
            quantity_available=quantity_available,
            unit=target.unit,
        )
        db.add(garage)
    elif garage.unit == target.unit and quantity_available > garage.quantity_available:
        garage.quantity_available = quantity_available
    await db.flush()
    return True


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
    return await _readiness_view(db, user_id=user.id, repair_session=repair_session)


@router.put(
    "/{session_id}/readiness/{requirement_definition_id}",
    response_model=RepairReadinessRead,
    dependencies=[CsrfDep],
)
async def update_repair_readiness(
    session_id: UUID,
    requirement_definition_id: UUID,
    payload: RepairReadinessUpdate,
    user: CurrentUserDep,
    db: AuthSessionDep,
    device_header: Annotated[str | None, Header(alias=DEVICE_HEADER)] = None,
    idempotency_header: Annotated[str | None, Header(alias=IDEMPOTENCY_HEADER)] = None,
) -> RepairReadinessRead:
    device_id = _parse_device_id(device_header)
    idempotency_key = _parse_idempotency_key(idempotency_header)
    request_data: dict[str, object] = {
        "requirement_definition_id": str(requirement_definition_id),
        **payload.model_dump(mode="json"),
    }
    fingerprint = _fingerprint(request_data)

    bundle, existing = await prepare_domain_mutation(
        db,
        user_id=user.id,
        session_id=session_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        event_type="readiness_state_changed",
    )
    if existing is not None:
        _assert_replay(existing, fingerprint)
        return await _readiness_view(
            db,
            user_id=user.id,
            repair_session=bundle.repair_session,
        )

    manifest = await _bound_manifest(
        db,
        user_id=user.id,
        repair_session=bundle.repair_session,
    )
    target = await _target_requirement(manifest, requirement_definition_id)
    quantity_available = _resolved_quantity(target, payload)

    state_row = await db.scalar(
        select(RepairRequirementState)
        .where(
            RepairRequirementState.user_id == user.id,
            RepairRequirementState.session_id == session_id,
            RepairRequirementState.requirement_definition_id == requirement_definition_id,
        )
        .with_for_update()
    )
    if state_row is None:
        state_row = RepairRequirementState(
            user_id=user.id,
            session_id=session_id,
            requirement_definition_id=requirement_definition_id,
            quantity_available=quantity_available,
            readiness_state=payload.readiness_state,
            procurement_reference=payload.procurement_reference,
            notes=payload.notes,
        )
        db.add(state_row)
    else:
        state_row.quantity_available = quantity_available
        state_row.readiness_state = payload.readiness_state
        state_row.procurement_reference = payload.procurement_reference
        state_row.notes = payload.notes

    garage_remembered = False
    if payload.readiness_state == "have":
        garage_remembered = await _remember_reusable_requirement(
            db,
            user_id=user.id,
            target=target,
            quantity_available=quantity_available,
        )
    await db.flush()

    await append_domain_event(
        db,
        bundle=bundle,
        user_id=user.id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        event_type="readiness_state_changed",
        payload={
            "requirement_definition_id": str(requirement_definition_id),
            "requirement_key": target.requirement_key,
            "readiness_state": payload.readiness_state,
            "quantity_available": str(quantity_available),
            "garage_remembered": garage_remembered,
            "request_fingerprint": fingerprint,
        },
    )
    return await _readiness_view(
        db,
        user_id=user.id,
        repair_session=bundle.repair_session,
    )
