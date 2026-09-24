import hashlib
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import aliased

from ..errors import ErrorCode, ErrorEnvelope, PartGraphError
from ..identity.auth.dependencies import AuthSessionDep, CurrentUserDep, require_csrf
from ..knowledge.completion_models import ProcedureActionMilestone, RepairDownstreamRequirement
from ..knowledge.models import ProcedureAction, RepairDefinition
from ..knowledge.repair_service import verified_requirement_manifest
from ..knowledge.support_boundaries import is_computer_service_boundary
from .completion_models import RepairDownstreamRequirementState
from .models import RepairProcedureActionState, RepairSession
from .readiness import DEVICE_HEADER, _parse_device_id
from .service import _bundle, _lease_expiry, _require_edit_lease, create_repair_session

CompletionStatus = Literal[
    "not_started",
    "active",
    "blocked",
    "physical_replacement_performed",
    "supported_work_complete",
    "downstream_required_pending",
    "unsupported_or_professional_pending",
    "fully_mechanically_complete",
    "archived",
]
DownstreamSupportState = Literal["supported", "professional_required", "unsupported"]
ResolutionKind = Literal["linked_session_complete", "external_service_confirmed"]


class DownstreamRequirementRead(BaseModel):
    requirement_id: UUID
    requirement_key: str
    title: str
    detail: str | None
    support_state: DownstreamSupportState
    target_repair_definition_id: UUID | None
    target_repair_key: str | None
    target_repair_title: str | None
    state: Literal["pending", "satisfied"]
    resolution_kind: ResolutionKind | None
    resolution_session_id: UUID | None
    resolution_note: str | None
    activated_at: datetime
    satisfied_at: datetime | None


class RepairCompletionRead(BaseModel):
    session_id: UUID
    repair_definition_id: UUID
    repair_title: str
    completion_status: CompletionStatus
    physical_replacement_expected: bool
    physical_replacement_performed: bool
    supported_partgraph_work_complete: bool
    downstream_required_pending: bool
    unsupported_or_professional_downstream_present: bool
    unsupported_or_professional_downstream_pending: bool
    fully_mechanically_complete: bool
    downstream_total: int
    downstream_pending: int
    downstream_satisfied: int
    unsupported_action_titles: list[str]
    downstream_requirements: list[DownstreamRequirementRead]


class DownstreamRequirementResolution(BaseModel):
    resolution_kind: ResolutionKind
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None


router = APIRouter(
    prefix="/api/v1/repair-sessions",
    tags=["Repair Completion"],
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
        code=ErrorCode.REPAIR_SESSION_STATE_CORRUPT,
        message=message,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


async def _owned_session_definition(
    db: AuthSessionDep,
    *,
    user_id: UUID,
    session_id: UUID,
) -> tuple[RepairSession, RepairDefinition]:
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
            message="Bind an exact verified repair definition before evaluating repair completion.",
            status_code=status.HTTP_409_CONFLICT,
        )
    definition = await db.get(RepairDefinition, repair_session.repair_definition_id)
    if definition is None:
        raise _integrity_error("Repair session definition is unavailable.")
    return repair_session, definition


async def _completion_view(
    db: AuthSessionDep,
    *,
    user_id: UUID,
    session_id: UUID,
) -> RepairCompletionRead:
    repair_session, definition = await _owned_session_definition(
        db,
        user_id=user_id,
        session_id=session_id,
    )
    actions = list(
        await db.scalars(
            select(ProcedureAction)
            .where(ProcedureAction.repair_definition_id == definition.id)
            .order_by(ProcedureAction.position)
        )
    )
    action_ids = [item.id for item in actions]
    progress_rows = (
        list(
            await db.scalars(
                select(RepairProcedureActionState).where(
                    RepairProcedureActionState.user_id == user_id,
                    RepairProcedureActionState.session_id == session_id,
                    RepairProcedureActionState.action_id.in_(action_ids),
                )
            )
        )
        if action_ids
        else []
    )
    progress = {item.action_id: item for item in progress_rows}

    boundary_actions = [item for item in actions if is_computer_service_boundary(item.action_key)]
    supported_actions = [item for item in actions if not is_computer_service_boundary(item.action_key)]
    supported_complete = bool(actions) and all(
        progress.get(item.id) is not None
        and progress[item.id].progress_state in {"completed", "skipped"}
        for item in supported_actions
    )
    blocked = any(item.progress_state == "blocked" for item in progress_rows)
    started = bool(progress_rows)

    milestone_action_ids = (
        set(
            await db.scalars(
                select(ProcedureActionMilestone.action_id).where(
                    ProcedureActionMilestone.action_id.in_(action_ids),
                    ProcedureActionMilestone.milestone_type == "physical_replacement",
                )
            )
        )
        if action_ids
        else set()
    )
    physical_replacement_performed = any(
        progress.get(action_id) is not None
        and progress[action_id].progress_state == "completed"
        for action_id in milestone_action_ids
    )

    target_definition = aliased(RepairDefinition)
    downstream_rows = (
        await db.execute(
            select(
                RepairDownstreamRequirementState,
                RepairDownstreamRequirement,
                target_definition,
            )
            .join(
                RepairDownstreamRequirement,
                RepairDownstreamRequirement.id
                == RepairDownstreamRequirementState.downstream_requirement_id,
            )
            .outerjoin(
                target_definition,
                target_definition.id == RepairDownstreamRequirement.target_repair_definition_id,
            )
            .where(
                RepairDownstreamRequirementState.user_id == user_id,
                RepairDownstreamRequirementState.session_id == session_id,
            )
            .order_by(RepairDownstreamRequirement.position)
        )
    ).all()

    downstream: list[DownstreamRequirementRead] = []
    downstream_pending = 0
    downstream_satisfied = 0
    unsupported_present = False
    unsupported_pending = False
    for state_row, requirement, target in downstream_rows:
        if requirement.support_state == "supported":
            if target is None:
                raise _integrity_error("Supported downstream work lost its target repair definition.")
            if target.vehicle_configuration_id != definition.vehicle_configuration_id:
                raise _integrity_error("Downstream repair target does not match the source vehicle configuration.")
        elif target is not None:
            raise _integrity_error("Outside-service downstream work cannot silently target a PartGraph repair.")

        is_pending = state_row.state == "pending"
        downstream_pending += int(is_pending)
        downstream_satisfied += int(not is_pending)
        if requirement.support_state != "supported":
            unsupported_present = True
            unsupported_pending = unsupported_pending or is_pending
        downstream.append(
            DownstreamRequirementRead(
                requirement_id=requirement.id,
                requirement_key=requirement.requirement_key,
                title=requirement.title,
                detail=requirement.detail,
                support_state=requirement.support_state,
                target_repair_definition_id=requirement.target_repair_definition_id,
                target_repair_key=None if target is None else target.repair_key,
                target_repair_title=None if target is None else target.title,
                state=state_row.state,
                resolution_kind=state_row.resolution_kind,
                resolution_session_id=state_row.resolution_session_id,
                resolution_note=state_row.resolution_note,
                activated_at=state_row.activated_at,
                satisfied_at=state_row.satisfied_at,
            )
        )

    unresolved_boundaries = [item.title for item in boundary_actions]
    fully_complete = (
        bool(actions)
        and supported_complete
        and not unresolved_boundaries
        and downstream_pending == 0
    )

    completion_status: CompletionStatus
    if repair_session.archived_at is not None:
        completion_status = "archived"
    elif fully_complete:
        completion_status = "fully_mechanically_complete"
    elif unsupported_pending or unresolved_boundaries:
        completion_status = "unsupported_or_professional_pending"
    elif downstream_pending > 0:
        completion_status = "downstream_required_pending"
    elif blocked:
        completion_status = "blocked"
    elif supported_complete:
        completion_status = "supported_work_complete"
    elif physical_replacement_performed:
        completion_status = "physical_replacement_performed"
    elif started:
        completion_status = "active"
    else:
        completion_status = "not_started"

    return RepairCompletionRead(
        session_id=session_id,
        repair_definition_id=definition.id,
        repair_title=definition.title,
        completion_status=completion_status,
        physical_replacement_expected=bool(milestone_action_ids),
        physical_replacement_performed=physical_replacement_performed,
        supported_partgraph_work_complete=supported_complete,
        downstream_required_pending=downstream_pending > 0,
        unsupported_or_professional_downstream_present=unsupported_present,
        unsupported_or_professional_downstream_pending=unsupported_pending,
        fully_mechanically_complete=fully_complete,
        downstream_total=len(downstream),
        downstream_pending=downstream_pending,
        downstream_satisfied=downstream_satisfied,
        unsupported_action_titles=unresolved_boundaries,
        downstream_requirements=downstream,
    )


async def _locked_downstream_state(
    db: AuthSessionDep,
    *,
    user_id: UUID,
    session_id: UUID,
    requirement_id: UUID,
) -> tuple[RepairDownstreamRequirementState, RepairDownstreamRequirement]:
    state_row = await db.scalar(
        select(RepairDownstreamRequirementState)
        .where(
            RepairDownstreamRequirementState.user_id == user_id,
            RepairDownstreamRequirementState.session_id == session_id,
            RepairDownstreamRequirementState.downstream_requirement_id == requirement_id,
        )
        .with_for_update()
    )
    if state_row is None:
        raise PartGraphError(
            code=ErrorCode.REQUEST_NOT_FOUND,
            message="Activated downstream requirement not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    requirement = await db.get(RepairDownstreamRequirement, requirement_id)
    if requirement is None:
        raise _integrity_error("Downstream requirement definition is unavailable.")
    return state_row, requirement


@router.get("/{session_id}/completion", response_model=RepairCompletionRead)
async def repair_completion(
    session_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
) -> RepairCompletionRead:
    return await _completion_view(db, user_id=user.id, session_id=session_id)


@router.post(
    "/{session_id}/completion/downstream/{requirement_id}/start",
    response_model=RepairCompletionRead,
    dependencies=[CsrfDep],
)
async def start_supported_downstream_repair(
    session_id: UUID,
    requirement_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
    device_header: Annotated[str | None, Header(alias=DEVICE_HEADER)] = None,
) -> RepairCompletionRead:
    device_id = _parse_device_id(device_header)
    source_bundle = await _bundle(db, user_id=user.id, session_id=session_id, for_update=True)
    _require_edit_lease(source_bundle.projection, device_id=device_id, now=datetime.now(UTC))
    state_row, requirement = await _locked_downstream_state(
        db,
        user_id=user.id,
        session_id=session_id,
        requirement_id=requirement_id,
    )
    if requirement.support_state != "supported" or requirement.target_repair_definition_id is None:
        raise PartGraphError(
            code=ErrorCode.REQUEST_VALIDATION_FAILED,
            message="Only supported downstream work can start a linked PartGraph repair.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    if state_row.state == "satisfied":
        return await _completion_view(db, user_id=user.id, session_id=session_id)
    if state_row.resolution_session_id is not None:
        return await _completion_view(db, user_id=user.id, session_id=session_id)

    _, source_definition = await _owned_session_definition(
        db,
        user_id=user.id,
        session_id=session_id,
    )
    target = await db.get(RepairDefinition, requirement.target_repair_definition_id)
    if target is None or target.status != "verified":
        raise _integrity_error("Supported downstream work no longer points to a current verified repair.")
    if target.vehicle_configuration_id != source_definition.vehicle_configuration_id:
        raise _integrity_error("Downstream repair target does not match the source vehicle configuration.")

    manifest = await verified_requirement_manifest(
        db,
        vehicle_configuration_id=target.vehicle_configuration_id,
        repair_key=target.repair_key,
    )
    if manifest.repair_definition_id != target.id:
        raise _integrity_error("Downstream repair target is no longer the current verified definition.")

    digest = hashlib.sha256(f"{session_id}:{requirement_id}".encode()).hexdigest()[:48]
    linked_bundle = await create_repair_session(
        db,
        user_id=user.id,
        user_vehicle_id=source_bundle.repair_session.user_vehicle_id,
        title=target.title,
        device_id=device_id,
        idempotency_key=f"downstream_{digest}",
    )
    if linked_bundle.repair_session.repair_definition_id is None:
        linked_bundle.repair_session.repair_definition_id = target.id
    elif linked_bundle.repair_session.repair_definition_id != target.id:
        raise _integrity_error("Linked downstream repair session is bound to the wrong definition.")
    state_row.resolution_session_id = linked_bundle.repair_session.id
    await db.flush()
    return await _completion_view(db, user_id=user.id, session_id=session_id)


@router.put(
    "/{session_id}/completion/downstream/{requirement_id}",
    response_model=RepairCompletionRead,
    dependencies=[CsrfDep],
)
async def satisfy_downstream_requirement(
    session_id: UUID,
    requirement_id: UUID,
    payload: DownstreamRequirementResolution,
    user: CurrentUserDep,
    db: AuthSessionDep,
    device_header: Annotated[str | None, Header(alias=DEVICE_HEADER)] = None,
) -> RepairCompletionRead:
    device_id = _parse_device_id(device_header)
    bundle = await _bundle(db, user_id=user.id, session_id=session_id, for_update=True)
    now = datetime.now(UTC)
    _require_edit_lease(bundle.projection, device_id=device_id, now=now)
    state_row, requirement = await _locked_downstream_state(
        db,
        user_id=user.id,
        session_id=session_id,
        requirement_id=requirement_id,
    )

    expected_kind: ResolutionKind = (
        "linked_session_complete"
        if requirement.support_state == "supported"
        else "external_service_confirmed"
    )
    if payload.resolution_kind != expected_kind:
        raise PartGraphError(
            code=ErrorCode.REQUEST_VALIDATION_FAILED,
            message=(
                "Supported downstream work must be completed through its linked PartGraph repair session."
                if requirement.support_state == "supported"
                else "Professional or unsupported work must be confirmed as completed externally."
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    if state_row.state == "satisfied":
        if state_row.resolution_kind != payload.resolution_kind:
            raise PartGraphError(
                code=ErrorCode.REQUEST_CONFLICT,
                message="This downstream requirement is already satisfied with a different resolution.",
                status_code=status.HTTP_409_CONFLICT,
            )
        return await _completion_view(db, user_id=user.id, session_id=session_id)

    if requirement.support_state == "supported":
        if state_row.resolution_session_id is None:
            raise PartGraphError(
                code=ErrorCode.REQUEST_CONFLICT,
                message="Start the linked PartGraph repair before resolving this requirement.",
                status_code=status.HTTP_409_CONFLICT,
            )
        linked_session = await db.scalar(
            select(RepairSession).where(
                RepairSession.id == state_row.resolution_session_id,
                RepairSession.user_id == user.id,
            )
        )
        if linked_session is None or linked_session.repair_definition_id != requirement.target_repair_definition_id:
            raise _integrity_error("Linked downstream repair session is unavailable or incorrectly bound.")
        linked_completion = await _completion_view(
            db,
            user_id=user.id,
            session_id=linked_session.id,
        )
        if not linked_completion.fully_mechanically_complete:
            raise PartGraphError(
                code=ErrorCode.REQUEST_CONFLICT,
                message="The linked PartGraph repair is not mechanically complete yet.",
                status_code=status.HTTP_409_CONFLICT,
            )
        state_row.resolution_note = None
    else:
        if state_row.resolution_session_id is not None:
            raise _integrity_error("Outside-service work cannot be resolved through a PartGraph repair session.")
        state_row.resolution_note = payload.note

    state_row.state = "satisfied"
    state_row.resolution_kind = payload.resolution_kind
    state_row.satisfied_at = now
    bundle.projection.editor_device_id = device_id
    bundle.projection.editor_lease_expires_at = _lease_expiry(now)
    bundle.projection.updated_at = now
    bundle.repair_session.updated_at = now
    await db.flush()
    return await _completion_view(db, user_id=user.id, session_id=session_id)
