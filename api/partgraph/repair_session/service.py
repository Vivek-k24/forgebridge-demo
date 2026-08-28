from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..errors import ErrorCode, PartGraphError
from ..user_vehicle.models import UserVehicle
from ..user_vehicle.schemas import UserVehicleRead
from ..user_vehicle.service import serialize_user_vehicle
from .models import RepairSession, RepairSessionEvent, RepairSessionProjection
from .schemas import (
    RepairSessionEventPage,
    RepairSessionEventRead,
    RepairSessionLeaseRead,
    RepairSessionMutationRead,
    RepairSessionRead,
    RepairSessionResumeRead,
)

logger = logging.getLogger("partgraph.repair_session")
PROJECTION_VERSION = 1
PROJECTION_REBUILT_CODE = "REPAIR_SESSION_PROJECTION_REBUILT"


@dataclass(frozen=True, slots=True)
class SessionBundle:
    repair_session: RepairSession
    projection: RepairSessionProjection


def _lease_expiry(now: datetime) -> datetime:
    return now + timedelta(seconds=settings.repair_edit_lease_seconds)


def _not_found() -> PartGraphError:
    return PartGraphError(
        code=ErrorCode.REPAIR_SESSION_NOT_FOUND,
        message="Repair session not found.",
        status_code=status.HTTP_404_NOT_FOUND,
    )


def _serialize_event(event: RepairSessionEvent) -> RepairSessionEventRead:
    return RepairSessionEventRead(
        id=event.id,
        session_id=event.session_id,
        sequence=event.sequence,
        event_type=event.event_type,
        actor_device_id=event.actor_device_id,
        payload=event.payload,
        created_at=event.created_at,
    )


def _serialize_session(bundle: SessionBundle) -> RepairSessionRead:
    item = bundle.repair_session
    projection = bundle.projection
    return RepairSessionRead(
        id=item.id,
        user_vehicle_id=item.user_vehicle_id,
        title=item.title,
        status=projection.status,
        current_sequence=projection.current_sequence,
        archived_at=item.archived_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def lease_view(
    projection: RepairSessionProjection,
    *,
    device_id: UUID | None,
    now: datetime | None = None,
) -> RepairSessionLeaseRead:
    current = now or datetime.now(UTC)
    if (
        projection.editor_device_id is None
        or projection.editor_lease_expires_at is None
        or projection.editor_lease_expires_at <= current
    ):
        return RepairSessionLeaseRead(status="available", can_edit=False, expires_at=None)
    if device_id is not None and projection.editor_device_id == device_id:
        return RepairSessionLeaseRead(
            status="owned",
            can_edit=True,
            expires_at=projection.editor_lease_expires_at,
        )
    return RepairSessionLeaseRead(
        status="held_by_other",
        can_edit=False,
        expires_at=projection.editor_lease_expires_at,
    )


async def _vehicle_for_session(
    session: AsyncSession,
    *,
    user_id: UUID,
    vehicle_id: UUID,
) -> UserVehicle:
    vehicle = await session.scalar(
        select(UserVehicle).where(
            UserVehicle.id == vehicle_id,
            UserVehicle.user_id == user_id,
        )
    )
    if vehicle is None:
        raise PartGraphError(
            code=ErrorCode.USER_VEHICLE_NOT_FOUND,
            message="Vehicle not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if vehicle.archived_at is not None:
        raise PartGraphError(
            code=ErrorCode.USER_VEHICLE_ARCHIVED,
            message="Archived vehicles cannot start new repair sessions.",
            status_code=status.HTTP_409_CONFLICT,
        )
    return vehicle


async def _bundle(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    for_update: bool = False,
) -> SessionBundle:
    session_statement = select(RepairSession).where(
        RepairSession.id == session_id,
        RepairSession.user_id == user_id,
    )
    projection_statement = select(RepairSessionProjection).where(
        RepairSessionProjection.session_id == session_id,
        RepairSessionProjection.user_id == user_id,
    )
    if for_update:
        session_statement = session_statement.with_for_update()
        projection_statement = projection_statement.with_for_update()

    repair_session = await session.scalar(session_statement)
    if repair_session is None:
        raise _not_found()
    projection = await session.scalar(projection_statement)
    if projection is None:
        if for_update:
            projection = await rebuild_projection(
                session,
                user_id=user_id,
                repair_session=repair_session,
            )
        else:
            return await _repair_missing_projection(
                session,
                user_id=user_id,
                repair_session=repair_session,
            )
    return SessionBundle(repair_session=repair_session, projection=projection)


async def _repair_missing_projection(
    session: AsyncSession,
    *,
    user_id: UUID,
    repair_session: RepairSession,
) -> SessionBundle:
    # A missing projection is a recoverable read-model failure. Lock the source
    # session before rebuilding so two resume requests cannot race the repair.
    locked = await session.scalar(
        select(RepairSession)
        .where(RepairSession.id == repair_session.id, RepairSession.user_id == user_id)
        .with_for_update()
    )
    if locked is None:
        raise _not_found()
    projection = await session.scalar(
        select(RepairSessionProjection)
        .where(
            RepairSessionProjection.session_id == repair_session.id,
            RepairSessionProjection.user_id == user_id,
        )
        .with_for_update()
    )
    if projection is None:
        projection = await rebuild_projection(session, user_id=user_id, repair_session=locked)
    return SessionBundle(repair_session=locked, projection=projection)


def _reduce_status(events: list[RepairSessionEvent]) -> str:
    current: str | None = None
    expected_sequence = 1
    for event in events:
        if event.sequence != expected_sequence:
            raise PartGraphError(
                code=ErrorCode.REPAIR_SESSION_STATE_CORRUPT,
                message="Repair session event history is incomplete.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        expected_sequence += 1
        if event.event_type == "session_started":
            if current is not None:
                raise PartGraphError(
                    code=ErrorCode.REPAIR_SESSION_STATE_CORRUPT,
                    message="Repair session event history is invalid.",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            current = "active"
        elif event.event_type == "session_paused":
            if current != "active":
                raise PartGraphError(
                    code=ErrorCode.REPAIR_SESSION_STATE_CORRUPT,
                    message="Repair session pause history is invalid.",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            current = "paused"
        elif event.event_type == "session_resumed":
            if current != "paused":
                raise PartGraphError(
                    code=ErrorCode.REPAIR_SESSION_STATE_CORRUPT,
                    message="Repair session resume history is invalid.",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            current = "active"
        elif event.event_type == "session_archived":
            if current not in {"active", "paused"}:
                raise PartGraphError(
                    code=ErrorCode.REPAIR_SESSION_STATE_CORRUPT,
                    message="Repair session archive history is invalid.",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            current = "archived"
        else:
            raise PartGraphError(
                code=ErrorCode.REPAIR_SESSION_STATE_CORRUPT,
                message="Repair session contains an unsupported event type.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    if current is None:
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_STATE_CORRUPT,
            message="Repair session has no event history.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return current


async def rebuild_projection(
    session: AsyncSession,
    *,
    user_id: UUID,
    repair_session: RepairSession,
) -> RepairSessionProjection:
    events = list(
        await session.scalars(
            select(RepairSessionEvent)
            .where(
                RepairSessionEvent.session_id == repair_session.id,
                RepairSessionEvent.user_id == user_id,
            )
            .order_by(RepairSessionEvent.sequence)
        )
    )
    status_value = _reduce_status(events)
    last_event = events[-1]
    now = datetime.now(UTC)
    projection = await session.get(RepairSessionProjection, repair_session.id)
    preserved_device: UUID | None = None
    preserved_expiry: datetime | None = None
    if (
        projection is not None
        and projection.editor_device_id is not None
        and projection.editor_lease_expires_at is not None
        and projection.editor_lease_expires_at > now
        and status_value != "archived"
    ):
        preserved_device = projection.editor_device_id
        preserved_expiry = projection.editor_lease_expires_at

    if projection is None:
        projection = RepairSessionProjection(session_id=repair_session.id, user_id=user_id)
        session.add(projection)
    projection.status = status_value
    projection.current_sequence = last_event.sequence
    projection.last_event_id = last_event.id
    projection.last_event_at = last_event.created_at
    projection.editor_device_id = preserved_device
    projection.editor_lease_expires_at = preserved_expiry
    projection.projection_version = PROJECTION_VERSION
    projection.updated_at = now

    archive_event = next(
        (event for event in reversed(events) if event.event_type == "session_archived"),
        None,
    )
    repair_session.archived_at = archive_event.created_at if archive_event is not None else None
    repair_session.updated_at = now
    await session.flush()
    logger.warning(
        "repair session projection rebuilt from immutable event history",
        extra={"code": PROJECTION_REBUILT_CODE, "repair_session_id": str(repair_session.id)},
    )
    return projection


async def _ensure_projection_current(
    session: AsyncSession,
    *,
    user_id: UUID,
    bundle: SessionBundle,
) -> SessionBundle:
    latest = await session.scalar(
        select(RepairSessionEvent)
        .where(
            RepairSessionEvent.session_id == bundle.repair_session.id,
            RepairSessionEvent.user_id == user_id,
        )
        .order_by(RepairSessionEvent.sequence.desc())
        .limit(1)
    )
    if latest is None:
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_STATE_CORRUPT,
            message="Repair session has no event history.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    projection = bundle.projection
    if (
        projection.projection_version == PROJECTION_VERSION
        and projection.current_sequence == latest.sequence
        and projection.last_event_id == latest.id
    ):
        return bundle
    locked = await _bundle(
        session,
        user_id=user_id,
        session_id=bundle.repair_session.id,
        for_update=True,
    )
    projection = await rebuild_projection(
        session,
        user_id=user_id,
        repair_session=locked.repair_session,
    )
    return SessionBundle(repair_session=locked.repair_session, projection=projection)


async def create_repair_session(
    session: AsyncSession,
    *,
    user_id: UUID,
    user_vehicle_id: UUID,
    title: str,
    device_id: UUID,
    idempotency_key: str,
) -> SessionBundle:
    await _vehicle_for_session(session, user_id=user_id, vehicle_id=user_vehicle_id)
    now = datetime.now(UTC)
    statement = (
        insert(RepairSession)
        .values(
            user_id=user_id,
            user_vehicle_id=user_vehicle_id,
            title=title,
            creation_idempotency_key=idempotency_key,
        )
        .on_conflict_do_nothing(constraint="uq_repair_sessions_owner_creation_key")
        .returning(RepairSession.id)
    )
    created_id = (await session.execute(statement)).scalar_one_or_none()
    if created_id is None:
        existing = await session.scalar(
            select(RepairSession).where(
                RepairSession.user_id == user_id,
                RepairSession.creation_idempotency_key == idempotency_key,
            )
        )
        if existing is None:
            raise PartGraphError(
                code=ErrorCode.REPAIR_SESSION_STATE_CONFLICT,
                message="Repair session could not be created safely.",
                status_code=status.HTTP_409_CONFLICT,
                retryable=True,
            )
        if existing.user_vehicle_id != user_vehicle_id or existing.title != title:
            raise PartGraphError(
                code=ErrorCode.REPAIR_SESSION_IDEMPOTENCY_CONFLICT,
                message="Idempotency key was already used for a different repair session request.",
                status_code=status.HTTP_409_CONFLICT,
            )
        return await _bundle(session, user_id=user_id, session_id=existing.id)

    repair_session = await session.get(RepairSession, created_id)
    if repair_session is None:
        raise RuntimeError("created repair session disappeared after insert")
    event = RepairSessionEvent(
        session_id=repair_session.id,
        user_id=user_id,
        sequence=1,
        event_type="session_started",
        idempotency_key=idempotency_key,
        actor_device_id=device_id,
        payload={"title": title, "user_vehicle_id": str(user_vehicle_id)},
    )
    session.add(event)
    await session.flush()
    projection = RepairSessionProjection(
        session_id=repair_session.id,
        user_id=user_id,
        status="active",
        current_sequence=1,
        last_event_id=event.id,
        last_event_at=event.created_at,
        editor_device_id=device_id,
        editor_lease_expires_at=_lease_expiry(now),
        projection_version=PROJECTION_VERSION,
        updated_at=now,
    )
    session.add(projection)
    repair_session.updated_at = now
    await session.flush()
    return SessionBundle(repair_session=repair_session, projection=projection)


async def list_repair_sessions(
    session: AsyncSession,
    *,
    user_id: UUID,
    vehicle_id: UUID | None,
    include_archived: bool,
    limit: int,
) -> list[SessionBundle]:
    statement = (
        select(RepairSession, RepairSessionProjection)
        .join(
            RepairSessionProjection,
            RepairSessionProjection.session_id == RepairSession.id,
        )
        .where(RepairSession.user_id == user_id)
    )
    if vehicle_id is not None:
        statement = statement.where(RepairSession.user_vehicle_id == vehicle_id)
    if not include_archived:
        statement = statement.where(RepairSession.archived_at.is_(None))
    rows = (
        await session.execute(statement.order_by(RepairSession.updated_at.desc()).limit(limit))
    ).all()
    return [SessionBundle(repair_session=row[0], projection=row[1]) for row in rows]


async def resume_repair_session(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    device_id: UUID | None,
) -> RepairSessionResumeRead:
    bundle = await _bundle(session, user_id=user_id, session_id=session_id)
    bundle = await _ensure_projection_current(session, user_id=user_id, bundle=bundle)
    vehicle = await session.scalar(
        select(UserVehicle).where(
            UserVehicle.id == bundle.repair_session.user_vehicle_id,
            UserVehicle.user_id == user_id,
        )
    )
    if vehicle is None:
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_STATE_CORRUPT,
            message="Repair session vehicle is unavailable.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    last_event = await session.get(RepairSessionEvent, bundle.projection.last_event_id)
    if last_event is None:
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_STATE_CORRUPT,
            message="Repair session last event is unavailable.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return RepairSessionResumeRead(
        session=_serialize_session(bundle),
        vehicle=UserVehicleRead.model_validate(serialize_user_vehicle(vehicle)),
        last_event=_serialize_event(last_event),
        lease=lease_view(bundle.projection, device_id=device_id),
    )


async def acquire_edit_lease(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    device_id: UUID,
    takeover: bool,
) -> SessionBundle:
    bundle = await _bundle(session, user_id=user_id, session_id=session_id, for_update=True)
    if bundle.projection.status == "archived":
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_ARCHIVED,
            message="Archived repair sessions are read-only.",
            status_code=status.HTTP_409_CONFLICT,
        )
    now = datetime.now(UTC)
    lease = lease_view(bundle.projection, device_id=device_id, now=now)
    if lease.status == "held_by_other" and not takeover:
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_LEASE_HELD,
            message="This repair session is being edited on another device.",
            status_code=status.HTTP_409_CONFLICT,
            details={"lease_expires_at": lease.expires_at.isoformat() if lease.expires_at else None},
        )
    bundle.projection.editor_device_id = device_id
    bundle.projection.editor_lease_expires_at = _lease_expiry(now)
    bundle.projection.updated_at = now
    await session.flush()
    return bundle


def _require_edit_lease(
    projection: RepairSessionProjection,
    *,
    device_id: UUID,
    now: datetime,
) -> None:
    if projection.status == "archived":
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_ARCHIVED,
            message="Archived repair sessions are read-only.",
            status_code=status.HTTP_409_CONFLICT,
        )
    lease = lease_view(projection, device_id=device_id, now=now)
    if lease.status == "available":
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_LEASE_REQUIRED,
            message="Acquire the repair-session edit lease before changing physical state.",
            status_code=status.HTTP_409_CONFLICT,
        )
    if lease.status == "held_by_other":
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_LEASE_HELD,
            message="This repair session is being edited on another device.",
            status_code=status.HTTP_409_CONFLICT,
            details={"lease_expires_at": lease.expires_at.isoformat() if lease.expires_at else None},
        )


async def _existing_idempotent_event(
    session: AsyncSession,
    *,
    session_id: UUID,
    user_id: UUID,
    idempotency_key: str,
    event_type: str,
) -> RepairSessionEvent | None:
    existing = await session.scalar(
        select(RepairSessionEvent).where(
            RepairSessionEvent.session_id == session_id,
            RepairSessionEvent.user_id == user_id,
            RepairSessionEvent.idempotency_key == idempotency_key,
        )
    )
    if existing is not None and existing.event_type != event_type:
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_IDEMPOTENCY_CONFLICT,
            message="Idempotency key was already used for a different repair-session action.",
            status_code=status.HTTP_409_CONFLICT,
        )
    return existing


async def append_status_event(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    device_id: UUID,
    idempotency_key: str,
    event_type: str,
) -> RepairSessionMutationRead:
    bundle = await _bundle(session, user_id=user_id, session_id=session_id, for_update=True)
    existing = await _existing_idempotent_event(
        session,
        session_id=session_id,
        user_id=user_id,
        idempotency_key=idempotency_key,
        event_type=event_type,
    )
    if existing is not None:
        return RepairSessionMutationRead(
            session=_serialize_session(bundle),
            event=_serialize_event(existing),
            lease=lease_view(bundle.projection, device_id=device_id),
        )

    now = datetime.now(UTC)
    _require_edit_lease(bundle.projection, device_id=device_id, now=now)
    current = bundle.projection.status
    target_status: str
    if event_type == "session_paused":
        if current != "active":
            raise PartGraphError(
                code=ErrorCode.REPAIR_SESSION_STATE_CONFLICT,
                message="Only an active repair session can be paused.",
                status_code=status.HTTP_409_CONFLICT,
            )
        target_status = "paused"
    elif event_type == "session_resumed":
        if current != "paused":
            raise PartGraphError(
                code=ErrorCode.REPAIR_SESSION_STATE_CONFLICT,
                message="Only a paused repair session can be resumed.",
                status_code=status.HTTP_409_CONFLICT,
            )
        target_status = "active"
    elif event_type == "session_archived":
        if current not in {"active", "paused"}:
            raise PartGraphError(
                code=ErrorCode.REPAIR_SESSION_STATE_CONFLICT,
                message="Repair session cannot be archived from its current state.",
                status_code=status.HTTP_409_CONFLICT,
            )
        target_status = "archived"
    else:
        raise PartGraphError(
            code=ErrorCode.REQUEST_VALIDATION_FAILED,
            message="Unsupported repair-session event type.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    event = RepairSessionEvent(
        session_id=session_id,
        user_id=user_id,
        sequence=bundle.projection.current_sequence + 1,
        event_type=event_type,
        idempotency_key=idempotency_key,
        actor_device_id=device_id,
        payload={},
    )
    session.add(event)
    await session.flush()

    bundle.projection.status = target_status
    bundle.projection.current_sequence = event.sequence
    bundle.projection.last_event_id = event.id
    bundle.projection.last_event_at = event.created_at
    bundle.projection.updated_at = now
    bundle.repair_session.updated_at = now
    if target_status == "archived":
        bundle.repair_session.archived_at = event.created_at
        bundle.projection.editor_device_id = None
        bundle.projection.editor_lease_expires_at = None
    else:
        bundle.projection.editor_device_id = device_id
        bundle.projection.editor_lease_expires_at = _lease_expiry(now)
    await session.flush()
    return RepairSessionMutationRead(
        session=_serialize_session(bundle),
        event=_serialize_event(event),
        lease=lease_view(bundle.projection, device_id=device_id),
    )


async def event_history(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    after_sequence: int,
    limit: int,
) -> RepairSessionEventPage:
    await _bundle(session, user_id=user_id, session_id=session_id)
    rows = list(
        await session.scalars(
            select(RepairSessionEvent)
            .where(
                RepairSessionEvent.session_id == session_id,
                RepairSessionEvent.user_id == user_id,
                RepairSessionEvent.sequence > after_sequence,
            )
            .order_by(RepairSessionEvent.sequence)
            .limit(limit + 1)
        )
    )
    has_more = len(rows) > limit
    items = rows[:limit]
    return RepairSessionEventPage(
        items=[_serialize_event(item) for item in items],
        next_after_sequence=items[-1].sequence if has_more and items else None,
    )


def serialize_session(bundle: SessionBundle) -> RepairSessionRead:
    return _serialize_session(bundle)
