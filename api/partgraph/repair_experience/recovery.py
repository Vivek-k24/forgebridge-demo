from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel
from sqlalchemy import select

from ..errors import ErrorCode, ErrorEnvelope, PartGraphError
from ..identity.auth.dependencies import AuthSessionDep, CurrentUserDep
from .models import RepairSession, RepairSessionEvent

IDEMPOTENCY_PATTERN = r"^[A-Za-z0-9_-]{8,64}$"
RecoveryState = Literal["committed", "unknown"]


class MutationRecoveryRead(BaseModel):
    session_id: UUID
    idempotency_key: str
    state: RecoveryState
    event_type: str | None = None
    sequence: int | None = None
    committed_at: datetime | None = None


class SessionCreationRecoveryRead(BaseModel):
    idempotency_key: str
    state: RecoveryState
    session_id: UUID | None = None
    created_at: datetime | None = None


router = APIRouter(
    prefix="/api/v1/repair-recovery",
    tags=["Repair Recovery"],
    responses={
        401: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope},
        422: {"model": ErrorEnvelope},
        500: {"model": ErrorEnvelope},
    },
)


@router.get(
    "/sessions/{session_id}/mutations/{idempotency_key}",
    response_model=MutationRecoveryRead,
)
async def recover_session_mutation(
    session_id: UUID,
    idempotency_key: Annotated[str, Path(pattern=IDEMPOTENCY_PATTERN)],
    user: CurrentUserDep,
    db: AuthSessionDep,
) -> MutationRecoveryRead:
    owned_session_id = await db.scalar(
        select(RepairSession.id).where(
            RepairSession.id == session_id,
            RepairSession.user_id == user.id,
        )
    )
    if owned_session_id is None:
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_NOT_FOUND,
            message="Repair session not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    event = await db.scalar(
        select(RepairSessionEvent).where(
            RepairSessionEvent.session_id == session_id,
            RepairSessionEvent.user_id == user.id,
            RepairSessionEvent.idempotency_key == idempotency_key,
        )
    )
    if event is None:
        return MutationRecoveryRead(
            session_id=session_id,
            idempotency_key=idempotency_key,
            state="unknown",
        )

    return MutationRecoveryRead(
        session_id=session_id,
        idempotency_key=idempotency_key,
        state="committed",
        event_type=event.event_type,
        sequence=event.sequence,
        committed_at=event.created_at,
    )


@router.get(
    "/session-creation/{idempotency_key}",
    response_model=SessionCreationRecoveryRead,
)
async def recover_session_creation(
    idempotency_key: Annotated[str, Path(pattern=IDEMPOTENCY_PATTERN)],
    user: CurrentUserDep,
    db: AuthSessionDep,
) -> SessionCreationRecoveryRead:
    repair_session = await db.scalar(
        select(RepairSession).where(
            RepairSession.user_id == user.id,
            RepairSession.creation_idempotency_key == idempotency_key,
        )
    )
    if repair_session is None:
        return SessionCreationRecoveryRead(
            idempotency_key=idempotency_key,
            state="unknown",
        )

    return SessionCreationRecoveryRead(
        idempotency_key=idempotency_key,
        state="committed",
        session_id=repair_session.id,
        created_at=repair_session.created_at,
    )
