import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status

from ..auth.dependencies import AuthSessionDep, CurrentUserDep, require_csrf
from ..errors import ErrorCode, ErrorEnvelope, PartGraphError
from .reorientation import build_reorientation
from .schemas import (
    RepairSessionCreate,
    RepairSessionEventPage,
    RepairSessionLeaseMutationRead,
    RepairSessionMutationRead,
    RepairSessionRead,
    RepairSessionResumeRead,
)
from .service import (
    acquire_edit_lease,
    append_status_event,
    create_repair_session,
    event_history,
    lease_view,
    list_repair_sessions,
    resume_repair_session,
    serialize_session,
)

DEVICE_HEADER = "X-PartGraph-Device-ID"
IDEMPOTENCY_HEADER = "Idempotency-Key"
IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")

ERROR_RESPONSES = {
    401: {"model": ErrorEnvelope},
    403: {"model": ErrorEnvelope},
    404: {"model": ErrorEnvelope},
    409: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
    500: {"model": ErrorEnvelope},
}
router = APIRouter(
    prefix="/api/v1/repair-sessions",
    tags=["Repair Sessions"],
    responses=ERROR_RESPONSES,
)
CsrfDep = Depends(require_csrf)


def _parse_device_id(value: str | None, *, required: bool) -> UUID | None:
    if value is None:
        if not required:
            return None
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


async def _complete_resume_snapshot(
    snapshot: RepairSessionResumeRead,
    *,
    user_id: UUID,
    db: AuthSessionDep,
) -> RepairSessionResumeRead:
    reorientation = await build_reorientation(
        db,
        user_id=user_id,
        session_id=snapshot.session.id,
        last_event=snapshot.last_event,
    )
    return snapshot.model_copy(update={"reorientation": reorientation})


@router.get("", response_model=list[RepairSessionRead])
async def sessions(
    user: CurrentUserDep,
    db: AuthSessionDep,
    vehicle_id: UUID | None = None,
    include_archived: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[RepairSessionRead]:
    rows = await list_repair_sessions(
        db,
        user_id=user.id,
        vehicle_id=vehicle_id,
        include_archived=include_archived,
        limit=limit,
    )
    return [serialize_session(row) for row in rows]


@router.post(
    "",
    response_model=RepairSessionResumeRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[CsrfDep],
)
async def create_session(
    payload: RepairSessionCreate,
    user: CurrentUserDep,
    db: AuthSessionDep,
    device_header: Annotated[str | None, Header(alias=DEVICE_HEADER)] = None,
    idempotency_header: Annotated[str | None, Header(alias=IDEMPOTENCY_HEADER)] = None,
) -> RepairSessionResumeRead:
    device_id = _parse_device_id(device_header, required=True)
    assert device_id is not None
    idempotency_key = _parse_idempotency_key(idempotency_header)
    bundle = await create_repair_session(
        db,
        user_id=user.id,
        user_vehicle_id=payload.user_vehicle_id,
        title=payload.title,
        device_id=device_id,
        idempotency_key=idempotency_key,
    )
    snapshot = await resume_repair_session(
        db,
        user_id=user.id,
        session_id=bundle.repair_session.id,
        device_id=device_id,
    )
    return await _complete_resume_snapshot(snapshot, user_id=user.id, db=db)


@router.get("/{session_id}/resume", response_model=RepairSessionResumeRead)
async def resume_snapshot(
    session_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
    device_header: Annotated[str | None, Header(alias=DEVICE_HEADER)] = None,
) -> RepairSessionResumeRead:
    device_id = _parse_device_id(device_header, required=False)
    snapshot = await resume_repair_session(
        db,
        user_id=user.id,
        session_id=session_id,
        device_id=device_id,
    )
    return await _complete_resume_snapshot(snapshot, user_id=user.id, db=db)


@router.get("/{session_id}/events", response_model=RepairSessionEventPage)
async def events(
    session_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
    after_sequence: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> RepairSessionEventPage:
    return await event_history(
        db,
        user_id=user.id,
        session_id=session_id,
        after_sequence=after_sequence,
        limit=limit,
    )


async def _lease_mutation(
    *,
    session_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
    device_header: str | None,
    takeover: bool,
) -> RepairSessionLeaseMutationRead:
    device_id = _parse_device_id(device_header, required=True)
    assert device_id is not None
    bundle = await acquire_edit_lease(
        db,
        user_id=user.id,
        session_id=session_id,
        device_id=device_id,
        takeover=takeover,
    )
    return RepairSessionLeaseMutationRead(
        session_id=session_id,
        lease=lease_view(bundle.projection, device_id=device_id),
    )


@router.post(
    "/{session_id}/lease/acquire",
    response_model=RepairSessionLeaseMutationRead,
    dependencies=[CsrfDep],
)
async def acquire_lease(
    session_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
    device_header: Annotated[str | None, Header(alias=DEVICE_HEADER)] = None,
) -> RepairSessionLeaseMutationRead:
    return await _lease_mutation(
        session_id=session_id,
        user=user,
        db=db,
        device_header=device_header,
        takeover=False,
    )


@router.post(
    "/{session_id}/lease/takeover",
    response_model=RepairSessionLeaseMutationRead,
    dependencies=[CsrfDep],
)
async def takeover_lease(
    session_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
    device_header: Annotated[str | None, Header(alias=DEVICE_HEADER)] = None,
) -> RepairSessionLeaseMutationRead:
    return await _lease_mutation(
        session_id=session_id,
        user=user,
        db=db,
        device_header=device_header,
        takeover=True,
    )


async def _status_mutation(
    *,
    session_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
    device_header: str | None,
    idempotency_header: str | None,
    event_type: str,
) -> RepairSessionMutationRead:
    device_id = _parse_device_id(device_header, required=True)
    assert device_id is not None
    return await append_status_event(
        db,
        user_id=user.id,
        session_id=session_id,
        device_id=device_id,
        idempotency_key=_parse_idempotency_key(idempotency_header),
        event_type=event_type,
    )


@router.post(
    "/{session_id}/pause",
    response_model=RepairSessionMutationRead,
    dependencies=[CsrfDep],
)
async def pause_session(
    session_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
    device_header: Annotated[str | None, Header(alias=DEVICE_HEADER)] = None,
    idempotency_header: Annotated[str | None, Header(alias=IDEMPOTENCY_HEADER)] = None,
) -> RepairSessionMutationRead:
    return await _status_mutation(
        session_id=session_id,
        user=user,
        db=db,
        device_header=device_header,
        idempotency_header=idempotency_header,
        event_type="session_paused",
    )


@router.post(
    "/{session_id}/resume",
    response_model=RepairSessionMutationRead,
    dependencies=[CsrfDep],
)
async def resume_session(
    session_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
    device_header: Annotated[str | None, Header(alias=DEVICE_HEADER)] = None,
    idempotency_header: Annotated[str | None, Header(alias=IDEMPOTENCY_HEADER)] = None,
) -> RepairSessionMutationRead:
    return await _status_mutation(
        session_id=session_id,
        user=user,
        db=db,
        device_header=device_header,
        idempotency_header=idempotency_header,
        event_type="session_resumed",
    )


@router.patch(
    "/{session_id}/archive",
    response_model=RepairSessionMutationRead,
    dependencies=[CsrfDep],
)
async def archive_session(
    session_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
    device_header: Annotated[str | None, Header(alias=DEVICE_HEADER)] = None,
    idempotency_header: Annotated[str | None, Header(alias=IDEMPOTENCY_HEADER)] = None,
) -> RepairSessionMutationRead:
    return await _status_mutation(
        session_id=session_id,
        user=user,
        db=db,
        device_header=device_header,
        idempotency_header=idempotency_header,
        event_type="session_archived",
    )
