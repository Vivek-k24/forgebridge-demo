from collections import defaultdict
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from ..auth.dependencies import AuthSessionDep, CurrentUserDep, require_csrf
from ..errors import ErrorCode, ErrorEnvelope, PartGraphError
from ..repair_definition.models import ProcedureAction, RepairDefinition, RequirementUse
from ..repair_definition.procedure_service import (
    REPAIR_PROCEDURE_INTEGRITY_ERROR,
    _procedure_for_definition,
)
from ..user_vehicle.models import UserVehicle
from .models import RepairProcedureActionState, RepairSession
from .readiness import (
    DEVICE_HEADER,
    IDEMPOTENCY_HEADER,
    _assert_replay,
    _fingerprint,
    _parse_device_id,
    _parse_idempotency_key,
    _readiness_view,
)
from .service import append_domain_event, prepare_domain_mutation

ProgressState = Literal["pending", "completed", "skipped", "blocked"]
PersistedProgressState = Literal["completed", "skipped", "blocked"]
GuidanceStatus = Literal[
    "action_available",
    "action_blocked",
    "inventory_blocked",
    "procedure_complete",
]
PROCEDURE_EVENT = "procedure_action_state_changed"


class GuidanceInventoryBlockerRead(BaseModel):
    requirement_definition_id: UUID
    requirement_key: str
    display_name: str
    readiness_state: str
    quantity_available: str
    required_quantity: str | None
    unit: str | None


class GuidanceActionRead(BaseModel):
    action_id: UUID
    action_key: str
    title: str
    instruction: str
    warning_text: str | None
    workspace_note: str | None
    position: int
    skippable: bool
    progress_state: ProgressState
    blocker_code: str | None
    notes: str | None
    dependency_action_keys: list[str]
    inventory_blockers: list[GuidanceInventoryBlockerRead]
    supporting_claim_ids: list[UUID]


class GuidanceSummaryRead(BaseModel):
    total: int
    completed: int
    skipped: int
    blocked: int
    pending: int


class RepairGuidanceRead(BaseModel):
    session_id: UUID
    repair_definition_id: UUID
    repair_key: str
    repair_title: str
    version: int
    definition_status: str
    capability_policy_key: str
    status: GuidanceStatus
    procedure_complete: bool
    current_action: GuidanceActionRead | None
    summary: GuidanceSummaryRead


class RepairGuidancePlanRead(RepairGuidanceRead):
    actions: list[GuidanceActionRead]


class GuidanceActionUpdate(BaseModel):
    progress_state: PersistedProgressState
    blocker_code: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("blocker_code")
    @classmethod
    def clean_blocker_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().lower().replace(" ", "_")
        return cleaned or None

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None


router = APIRouter(
    prefix="/api/v1/repair-sessions",
    tags=["Guided Repair"],
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


def _integrity_error(message: str) -> PartGraphError:
    return PartGraphError(
        code=REPAIR_PROCEDURE_INTEGRITY_ERROR,
        message=message,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


async def _session_context(
    db: AuthSessionDep,
    *,
    user_id: UUID,
    session_id: UUID,
) -> tuple[RepairSession, UserVehicle, RepairDefinition]:
    repair_session = await db.scalar(
        select(RepairSession).where(
            RepairSession.id == session_id,
            RepairSession.user_id == user_id,
        )
    )
    if repair_session is None:
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_NOT_FOUND,
            message="Repair session not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if repair_session.repair_definition_id is None:
        raise PartGraphError(
            code="REPAIR_PROCEDURE_NOT_AVAILABLE",
            message="Bind an exact verified repair definition before opening guided repair.",
            status_code=status.HTTP_409_CONFLICT,
        )

    vehicle = await db.scalar(
        select(UserVehicle).where(
            UserVehicle.id == repair_session.user_vehicle_id,
            UserVehicle.user_id == user_id,
        )
    )
    if vehicle is None or vehicle.canonical_configuration_id is None:
        raise _integrity_error(
            "Guided repair session no longer has an exact canonical vehicle configuration."
        )

    definition = await db.scalar(
        select(RepairDefinition).where(
            RepairDefinition.id == repair_session.repair_definition_id,
            RepairDefinition.vehicle_configuration_id == vehicle.canonical_configuration_id,
        )
    )
    if definition is None or definition.status not in {"verified", "superseded"}:
        raise _integrity_error(
            "Bound repair definition no longer matches the session vehicle configuration."
        )
    return repair_session, vehicle, definition


async def _guidance_view(
    db: AuthSessionDep,
    *,
    user_id: UUID,
    session_id: UUID,
    include_plan: bool,
) -> RepairGuidanceRead | RepairGuidancePlanRead:
    repair_session, _, definition = await _session_context(
        db,
        user_id=user_id,
        session_id=session_id,
    )
    procedure = await _procedure_for_definition(
        db,
        definition=definition,
        allowed_claim_states={"verified", "superseded"},
    )

    action_ids = [item.action_id for item in procedure.actions]
    action_rows = list(
        await db.scalars(select(ProcedureAction).where(ProcedureAction.id.in_(action_ids)))
    )
    action_models = {item.id: item for item in action_rows}
    if set(action_models) != set(action_ids):
        raise _integrity_error("Guided procedure lost canonical action identity.")

    progress_rows = list(
        await db.scalars(
            select(RepairProcedureActionState).where(
                RepairProcedureActionState.user_id == user_id,
                RepairProcedureActionState.session_id == session_id,
                RepairProcedureActionState.action_id.in_(action_ids),
            )
        )
    )
    progress = {item.action_id: item for item in progress_rows}

    readiness = await _readiness_view(
        db,
        user_id=user_id,
        repair_session=repair_session,
    )
    readiness_by_definition = {
        item.requirement_definition_id: item for item in readiness.requirements
    }

    all_use_ids = {
        use_id for action in procedure.actions for use_id in action.required_use_ids
    }
    use_rows = (
        list(
            await db.scalars(
                select(RequirementUse).where(RequirementUse.id.in_(all_use_ids))
            )
        )
        if all_use_ids
        else []
    )
    use_by_id = {item.id: item for item in use_rows}
    if set(use_by_id) != all_use_ids:
        raise _integrity_error("Guided action requirement identity is incomplete.")

    state_by_key: dict[str, ProgressState] = {}
    details_by_action: dict[UUID, tuple[str | None, str | None]] = {}
    for item in procedure.actions:
        row = progress.get(item.action_id)
        state = cast(ProgressState, "pending" if row is None else row.progress_state)
        if state == "skipped" and not action_models[item.action_id].skippable:
            raise _integrity_error("A non-skippable canonical action is recorded as skipped.")
        state_by_key[item.action_key] = state
        details_by_action[item.action_id] = (
            None if row is None else row.blocker_code,
            None if row is None else row.notes,
        )

    blockers_by_action: dict[UUID, list[GuidanceInventoryBlockerRead]] = defaultdict(list)
    for item in procedure.actions:
        seen: set[UUID] = set()
        for use_id in item.required_use_ids:
            requirement_use = use_by_id[use_id]
            if requirement_use.necessity != "required":
                continue
            requirement_id = requirement_use.requirement_definition_id
            if requirement_id in seen:
                continue
            seen.add(requirement_id)
            readiness_item = readiness_by_definition.get(requirement_id)
            if readiness_item is None:
                raise _integrity_error(
                    "Guided action requirement is absent from the bound readiness manifest."
                )
            if readiness_item.readiness_state == "have":
                continue
            blockers_by_action[item.action_id].append(
                GuidanceInventoryBlockerRead(
                    requirement_definition_id=requirement_id,
                    requirement_key=readiness_item.requirement_key,
                    display_name=readiness_item.display_name,
                    readiness_state=readiness_item.readiness_state,
                    quantity_available=str(readiness_item.quantity_available),
                    required_quantity=(
                        None
                        if readiness_item.required_quantity is None
                        else str(readiness_item.required_quantity)
                    ),
                    unit=readiness_item.unit,
                )
            )

    action_reads: list[GuidanceActionRead] = []
    for item in procedure.actions:
        blocker_code, notes = details_by_action[item.action_id]
        action_reads.append(
            GuidanceActionRead(
                action_id=item.action_id,
                action_key=item.action_key,
                title=item.title,
                instruction=item.instruction,
                warning_text=item.warning_text,
                workspace_note=item.workspace_note,
                position=item.position,
                skippable=action_models[item.action_id].skippable,
                progress_state=state_by_key[item.action_key],
                blocker_code=blocker_code,
                notes=notes,
                dependency_action_keys=item.dependency_action_keys,
                inventory_blockers=blockers_by_action[item.action_id],
                supporting_claim_ids=item.supporting_claim_ids,
            )
        )

    completed = sum(item.progress_state == "completed" for item in action_reads)
    skipped = sum(item.progress_state == "skipped" for item in action_reads)
    blocked = sum(item.progress_state == "blocked" for item in action_reads)
    pending = sum(item.progress_state == "pending" for item in action_reads)

    current: GuidanceActionRead | None = None
    for item in action_reads:
        if item.progress_state in {"completed", "skipped"}:
            continue
        if not all(
            state_by_key.get(dependency) in {"completed", "skipped"}
            for dependency in item.dependency_action_keys
        ):
            continue
        current = item
        break

    procedure_complete = completed + skipped == len(action_reads)
    if current is None and not procedure_complete:
        unresolved = [
            key
            for key, state in state_by_key.items()
            if state not in {"completed", "skipped"}
        ]
        raise _integrity_error(
            "No deterministic next action can be selected from procedure progress: "
            + ", ".join(unresolved)
        )

    guidance_status: GuidanceStatus
    if procedure_complete:
        guidance_status = "procedure_complete"
    elif current is not None and current.progress_state == "blocked":
        guidance_status = "action_blocked"
    elif current is not None and current.inventory_blockers:
        guidance_status = "inventory_blocked"
    else:
        guidance_status = "action_available"

    common = dict(
        session_id=session_id,
        repair_definition_id=procedure.repair_definition_id,
        repair_key=procedure.repair_key,
        repair_title=procedure.title,
        version=procedure.version,
        definition_status=procedure.definition_status,
        capability_policy_key=procedure.capability_policy_key,
        status=guidance_status,
        procedure_complete=procedure_complete,
        current_action=current,
        summary=GuidanceSummaryRead(
            total=len(action_reads),
            completed=completed,
            skipped=skipped,
            blocked=blocked,
            pending=pending,
        ),
    )
    if include_plan:
        return RepairGuidancePlanRead(**common, actions=action_reads)
    return RepairGuidanceRead(**common)


@router.get("/{session_id}/guidance", response_model=RepairGuidanceRead)
async def current_guidance(
    session_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
) -> RepairGuidanceRead:
    result = await _guidance_view(
        db,
        user_id=user.id,
        session_id=session_id,
        include_plan=False,
    )
    assert isinstance(result, RepairGuidanceRead)
    return result


@router.get("/{session_id}/guidance/plan", response_model=RepairGuidancePlanRead)
async def guidance_plan(
    session_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
) -> RepairGuidancePlanRead:
    result = await _guidance_view(
        db,
        user_id=user.id,
        session_id=session_id,
        include_plan=True,
    )
    assert isinstance(result, RepairGuidancePlanRead)
    return result


@router.put(
    "/{session_id}/guidance/actions/{action_id}",
    response_model=RepairGuidanceRead,
    dependencies=[CsrfDep],
)
async def update_action_progress(
    session_id: UUID,
    action_id: UUID,
    payload: GuidanceActionUpdate,
    user: CurrentUserDep,
    db: AuthSessionDep,
    device_header: Annotated[str | None, Header(alias=DEVICE_HEADER)] = None,
    idempotency_header: Annotated[str | None, Header(alias=IDEMPOTENCY_HEADER)] = None,
) -> RepairGuidanceRead:
    device_id = _parse_device_id(device_header)
    idempotency_key = _parse_idempotency_key(idempotency_header)
    request_data: dict[str, object] = {
        "action_id": str(action_id),
        **payload.model_dump(mode="json"),
    }
    fingerprint = _fingerprint(request_data)

    bundle, existing_event = await prepare_domain_mutation(
        db,
        user_id=user.id,
        session_id=session_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        event_type=PROCEDURE_EVENT,
    )
    if existing_event is not None:
        _assert_replay(existing_event, fingerprint)
        replay = await _guidance_view(
            db,
            user_id=user.id,
            session_id=session_id,
            include_plan=False,
        )
        assert isinstance(replay, RepairGuidanceRead)
        return replay

    before = await _guidance_view(
        db,
        user_id=user.id,
        session_id=session_id,
        include_plan=False,
    )
    assert isinstance(before, RepairGuidanceRead)
    current = before.current_action
    if current is None or current.action_id != action_id:
        raise PartGraphError(
            code="REPAIR_PROCEDURE_ACTION_NOT_CURRENT",
            message="Only the current deterministic guided action can be changed.",
            status_code=status.HTTP_409_CONFLICT,
        )

    if payload.progress_state == "completed" and current.inventory_blockers:
        raise PartGraphError(
            code="REPAIR_PROCEDURE_ACTION_INVENTORY_BLOCKED",
            message="Resolve required Inventory blockers before completing this action.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "requirement_definition_ids": [
                    str(item.requirement_definition_id)
                    for item in current.inventory_blockers
                ]
            },
        )
    if payload.progress_state == "skipped" and not current.skippable:
        raise PartGraphError(
            code="REPAIR_PROCEDURE_ACTION_NOT_SKIPPABLE",
            message="This verified action is not marked skippable.",
            status_code=status.HTTP_409_CONFLICT,
        )

    state_row = await db.scalar(
        select(RepairProcedureActionState)
        .where(
            RepairProcedureActionState.user_id == user.id,
            RepairProcedureActionState.session_id == session_id,
            RepairProcedureActionState.action_id == action_id,
        )
        .with_for_update()
    )
    previous_state: ProgressState = (
        "pending" if state_row is None else cast(ProgressState, state_row.progress_state)
    )
    if previous_state in {"completed", "skipped"}:
        raise PartGraphError(
            code="REPAIR_PROCEDURE_ACTION_STATE_CONFLICT",
            message="Completed or skipped actions require an explicit future undo workflow.",
            status_code=status.HTTP_409_CONFLICT,
        )

    blocker_code = payload.blocker_code if payload.progress_state == "blocked" else None
    notes = payload.notes
    if state_row is None:
        state_row = RepairProcedureActionState(
            user_id=user.id,
            session_id=session_id,
            action_id=action_id,
            progress_state=payload.progress_state,
            blocker_code=blocker_code,
            notes=notes,
        )
        db.add(state_row)
    else:
        state_row.progress_state = payload.progress_state
        state_row.blocker_code = blocker_code
        state_row.notes = notes
    await db.flush()

    await append_domain_event(
        db,
        bundle=bundle,
        user_id=user.id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        event_type=PROCEDURE_EVENT,
        payload={
            "request_fingerprint": fingerprint,
            "action_id": str(action_id),
            "action_key": current.action_key,
            "previous_state": previous_state,
            "progress_state": payload.progress_state,
            "blocker_code": blocker_code,
            "notes": notes,
        },
    )
    await db.flush()

    result = await _guidance_view(
        db,
        user_id=user.id,
        session_id=session_id,
        include_plan=False,
    )
    assert isinstance(result, RepairGuidanceRead)
    return result
