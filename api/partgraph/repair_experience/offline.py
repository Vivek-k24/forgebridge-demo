from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import status
from pydantic import BaseModel
from sqlalchemy import select

from ..errors import ErrorCode, PartGraphError
from ..identity.auth.dependencies import AuthSessionDep
from .guidance import RepairGuidancePlanRead, _guidance_view
from .models import RepairSession, RepairSessionEvent
from .readiness import RepairReadinessRead, _readiness_view
from .reorientation import build_reorientation
from .schemas import RepairSessionResumeRead
from .service import resume_repair_session

OFFLINE_PACK_SCHEMA_VERSION = 1


class RepairOfflinePackRead(BaseModel):
    schema_version: Literal[1] = OFFLINE_PACK_SCHEMA_VERSION
    pack_version: str
    read_only: Literal[True] = True
    generated_at: datetime
    owner_id: UUID
    session_id: UUID
    server_sequence: int
    repair_definition_id: UUID
    repair_definition_version: int
    definition_status: str
    resume: RepairSessionResumeRead
    readiness: RepairReadinessRead
    guidance: RepairGuidancePlanRead


async def build_offline_repair_pack(
    db: AuthSessionDep,
    *,
    user_id: UUID,
    session_id: UUID,
) -> RepairOfflinePackRead:
    snapshot = await resume_repair_session(
        db,
        user_id=user_id,
        session_id=session_id,
        device_id=None,
    )

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
            code=ErrorCode.OFFLINE_REPAIR_PACK_UNAVAILABLE,
            message="Bind an exact verified repair definition before creating an offline repair pack.",
            status_code=status.HTTP_409_CONFLICT,
        )

    last_event = await db.scalar(
        select(RepairSessionEvent).where(
            RepairSessionEvent.id == snapshot.last_event.id,
            RepairSessionEvent.session_id == session_id,
            RepairSessionEvent.user_id == user_id,
        )
    )
    if last_event is None:
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_STATE_CORRUPT,
            message="Repair session last event is unavailable.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    reorientation = await build_reorientation(
        db,
        user_id=user_id,
        session_id=session_id,
        last_event=last_event,
    )
    snapshot = snapshot.model_copy(update={"reorientation": reorientation})

    readiness = await _readiness_view(
        db,
        user_id=user_id,
        repair_session=repair_session,
    )
    if readiness.binding_status != "bound" or readiness.repair is None:
        raise PartGraphError(
            code=ErrorCode.OFFLINE_REPAIR_PACK_UNAVAILABLE,
            message="A verified bound repair is required before creating an offline repair pack.",
            status_code=status.HTTP_409_CONFLICT,
        )

    guidance = await _guidance_view(
        db,
        user_id=user_id,
        session_id=session_id,
        include_plan=True,
    )
    assert isinstance(guidance, RepairGuidancePlanRead)

    pack_version = (
        f"rp{OFFLINE_PACK_SCHEMA_VERSION}:"
        f"{guidance.repair_definition_id}:"
        f"v{guidance.version}:"
        f"s{snapshot.session.current_sequence}"
    )
    return RepairOfflinePackRead(
        pack_version=pack_version,
        generated_at=datetime.now(UTC),
        owner_id=user_id,
        session_id=session_id,
        server_sequence=snapshot.session.current_sequence,
        repair_definition_id=guidance.repair_definition_id,
        repair_definition_version=guidance.version,
        definition_status=guidance.definition_status,
        resume=snapshot,
        readiness=readiness,
        guidance=guidance,
    )
