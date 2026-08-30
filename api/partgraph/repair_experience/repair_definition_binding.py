from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import AuthSessionDep, CurrentUserDep, require_csrf
from ..errors import ErrorCode, ErrorEnvelope, PartGraphError
from ..repair_definition.models import RepairDefinition
from ..repair_definition.service import verified_requirement_manifest
from ..user_vehicle.models import UserVehicle
from .models import RepairSession, RepairSessionProjection
from .service import lease_view, rebuild_projection

DEVICE_HEADER = "X-PartGraph-Device-ID"
REPAIR_DEFINITION_VEHICLE_UNRESOLVED = "REPAIR_DEFINITION_VEHICLE_UNRESOLVED"
REPAIR_DEFINITION_BINDING_CONFLICT = "REPAIR_DEFINITION_BINDING_CONFLICT"
REPAIR_DEFINITION_INTEGRITY_ERROR = "REPAIR_DEFINITION_INTEGRITY_ERROR"


class RepairDefinitionBind(BaseModel):
    repair_key: str = Field(
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    )

    @field_validator("repair_key")
    @classmethod
    def normalize_repair_key(cls, value: str) -> str:
        return value.strip().lower()


class RepairDefinitionBindingRead(BaseModel):
    session_id: UUID
    repair_definition_id: UUID
    vehicle_configuration_id: UUID
    repair_key: str
    title: str
    version: int
    binding_state: Literal["bound", "already_bound"]


class RepairDefinitionOptionRead(BaseModel):
    repair_definition_id: UUID
    repair_key: str
    title: str
    version: int


class RepairDefinitionOptionsRead(BaseModel):
    session_id: UUID
    vehicle_resolution: Literal["exact", "unresolved"]
    options: list[RepairDefinitionOptionRead]


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


async def _owned_session(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
) -> RepairSession:
    repair_session = await session.scalar(
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
    return repair_session


async def _locked_session(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
) -> tuple[RepairSession, RepairSessionProjection]:
    repair_session = await session.scalar(
        select(RepairSession)
        .where(
            RepairSession.id == session_id,
            RepairSession.user_id == user_id,
        )
        .with_for_update()
    )
    if repair_session is None:
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_NOT_FOUND,
            message="Repair session not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    projection = await session.scalar(
        select(RepairSessionProjection)
        .where(
            RepairSessionProjection.session_id == session_id,
            RepairSessionProjection.user_id == user_id,
        )
        .with_for_update()
    )
    if projection is None:
        projection = await rebuild_projection(
            session,
            user_id=user_id,
            repair_session=repair_session,
        )
    return repair_session, projection


def _require_edit_lease(projection: RepairSessionProjection, *, device_id: UUID) -> None:
    if projection.status == "archived":
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_ARCHIVED,
            message="Archived repair sessions are read-only.",
            status_code=status.HTTP_409_CONFLICT,
        )

    lease = lease_view(projection, device_id=device_id, now=datetime.now(UTC))
    if lease.status == "available":
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_LEASE_REQUIRED,
            message="Acquire the repair-session edit lease before binding verified repair truth.",
            status_code=status.HTTP_409_CONFLICT,
        )
    if lease.status == "held_by_other":
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_LEASE_HELD,
            message="This repair session is being edited on another device.",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "lease_expires_at": lease.expires_at.isoformat() if lease.expires_at else None
            },
        )


@router.get("/{session_id}/repair-options", response_model=RepairDefinitionOptionsRead)
async def repair_options(
    session_id: UUID,
    user: CurrentUserDep,
    db: AuthSessionDep,
) -> RepairDefinitionOptionsRead:
    repair_session = await _owned_session(db, user_id=user.id, session_id=session_id)
    vehicle = await db.scalar(
        select(UserVehicle).where(
            UserVehicle.id == repair_session.user_vehicle_id,
            UserVehicle.user_id == user.id,
        )
    )
    if vehicle is None:
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_STATE_CORRUPT,
            message="Repair session vehicle ownership is inconsistent.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    if vehicle.canonical_configuration_id is None:
        return RepairDefinitionOptionsRead(
            session_id=session_id,
            vehicle_resolution="unresolved",
            options=[],
        )

    definitions = list(
        await db.scalars(
            select(RepairDefinition)
            .where(
                RepairDefinition.vehicle_configuration_id == vehicle.canonical_configuration_id,
                RepairDefinition.status == "verified",
            )
            .order_by(RepairDefinition.title, RepairDefinition.repair_key, RepairDefinition.version)
        )
    )
    seen: set[str] = set()
    options: list[RepairDefinitionOptionRead] = []
    for definition in definitions:
        if definition.repair_key in seen:
            raise PartGraphError(
                code=REPAIR_DEFINITION_INTEGRITY_ERROR,
                message=(
                    "Multiple current verified repair definitions exist for the same vehicle "
                    "and repair."
                ),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        seen.add(definition.repair_key)
        options.append(
            RepairDefinitionOptionRead(
                repair_definition_id=definition.id,
                repair_key=definition.repair_key,
                title=definition.title,
                version=definition.version,
            )
        )
    return RepairDefinitionOptionsRead(
        session_id=session_id,
        vehicle_resolution="exact",
        options=options,
    )


@router.put(
    "/{session_id}/repair-definition",
    response_model=RepairDefinitionBindingRead,
    dependencies=[CsrfDep],
)
async def bind_repair_definition(
    session_id: UUID,
    payload: RepairDefinitionBind,
    user: CurrentUserDep,
    db: AuthSessionDep,
    device_header: Annotated[str | None, Header(alias=DEVICE_HEADER)] = None,
) -> RepairDefinitionBindingRead:
    device_id = _parse_device_id(device_header)
    repair_session, projection = await _locked_session(
        db,
        user_id=user.id,
        session_id=session_id,
    )
    _require_edit_lease(projection, device_id=device_id)

    vehicle = await db.scalar(
        select(UserVehicle).where(
            UserVehicle.id == repair_session.user_vehicle_id,
            UserVehicle.user_id == user.id,
        )
    )
    if vehicle is None:
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_STATE_CORRUPT,
            message="Repair session vehicle ownership is inconsistent.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    if vehicle.canonical_configuration_id is None:
        raise PartGraphError(
            code=REPAIR_DEFINITION_VEHICLE_UNRESOLVED,
            message=(
                "This saved vehicle is not resolved to an exact canonical configuration, "
                "so verified repair requirements cannot be bound safely."
            ),
            status_code=status.HTTP_409_CONFLICT,
        )

    manifest = await verified_requirement_manifest(
        db,
        vehicle_configuration_id=vehicle.canonical_configuration_id,
        repair_key=payload.repair_key,
    )

    if repair_session.repair_definition_id is None:
        repair_session.repair_definition_id = manifest.repair_definition_id
        repair_session.updated_at = datetime.now(UTC)
        await db.flush()
        binding_state: Literal["bound", "already_bound"] = "bound"
    elif repair_session.repair_definition_id == manifest.repair_definition_id:
        binding_state = "already_bound"
    else:
        raise PartGraphError(
            code=REPAIR_DEFINITION_BINDING_CONFLICT,
            message=(
                "This repair session is already bound to a different verified repair "
                "definition and cannot be silently re-bound."
            ),
            status_code=status.HTTP_409_CONFLICT,
            details={"current_repair_definition_id": str(repair_session.repair_definition_id)},
        )

    return RepairDefinitionBindingRead(
        session_id=repair_session.id,
        repair_definition_id=manifest.repair_definition_id,
        vehicle_configuration_id=manifest.vehicle_configuration_id,
        repair_key=manifest.repair_key,
        title=manifest.title,
        version=manifest.version,
        binding_state=binding_state,
    )
