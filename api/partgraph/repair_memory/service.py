from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import ErrorCode, PartGraphError
from ..repair_session.models import RepairSession, RepairSessionEvent
from ..repair_session.service import append_domain_event, prepare_domain_mutation
from .models import (
    RepairFastener,
    RepairInventoryItem,
    RepairObservation,
    RepairPhotoEvidence,
    RepairStorageLocation,
)
from .schemas import (
    FastenerCreate,
    FastenerRead,
    FastenerStateUpdate,
    InventoryItemCreate,
    InventoryItemRead,
    InventoryStateUpdate,
    ObservationCreate,
    ObservationRead,
    PhotoDeleteRead,
    PhotoEvidenceRead,
    PhotoPurpose,
    StorageLocationCreate,
    StorageLocationRead,
)
from .storage import (
    PhotoFormatError,
    delete_photo_file,
    detect_photo_media_type,
    new_storage_key,
    photo_path,
    store_photo,
)


def _fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _clean_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    name = Path(filename).name
    printable = "".join(character for character in name if character.isprintable()).strip()
    return printable[:255] or None


def _assert_replay(event: RepairSessionEvent, fingerprint: str) -> None:
    if event.payload.get("request_fingerprint") != fingerprint:
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_IDEMPOTENCY_CONFLICT,
            message="Idempotency key was already used with different repair-memory data.",
            status_code=status.HTTP_409_CONFLICT,
        )


def _payload_uuid(event: RepairSessionEvent, key: str) -> UUID:
    value = event.payload.get(key)
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_STATE_CORRUPT,
            message="Repair-memory event is missing its resource reference.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc


async def _require_session(session: AsyncSession, *, user_id: UUID, session_id: UUID) -> None:
    row = await session.scalar(
        select(RepairSession.id).where(
            RepairSession.id == session_id,
            RepairSession.user_id == user_id,
        )
    )
    if row is None:
        raise PartGraphError(
            code=ErrorCode.REPAIR_SESSION_NOT_FOUND,
            message="Repair session not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


async def _storage_location(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    location_id: UUID,
) -> RepairStorageLocation:
    row = await session.scalar(
        select(RepairStorageLocation).where(
            RepairStorageLocation.id == location_id,
            RepairStorageLocation.user_id == user_id,
            RepairStorageLocation.session_id == session_id,
        )
    )
    if row is None:
        raise PartGraphError(
            code=ErrorCode.STORAGE_LOCATION_NOT_FOUND,
            message="Storage location not found in this repair session.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return row


async def _fastener(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    fastener_id: UUID,
) -> RepairFastener:
    row = await session.scalar(
        select(RepairFastener).where(
            RepairFastener.id == fastener_id,
            RepairFastener.user_id == user_id,
            RepairFastener.session_id == session_id,
        )
    )
    if row is None:
        raise PartGraphError(
            code=ErrorCode.FASTENER_NOT_FOUND,
            message="Fastener or small part not found in this repair session.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return row


async def _inventory_item(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    item_id: UUID,
) -> RepairInventoryItem:
    row = await session.scalar(
        select(RepairInventoryItem).where(
            RepairInventoryItem.id == item_id,
            RepairInventoryItem.user_id == user_id,
            RepairInventoryItem.session_id == session_id,
        )
    )
    if row is None:
        raise PartGraphError(
            code=ErrorCode.INVENTORY_ITEM_NOT_FOUND,
            message="Inventory item not found in this repair session.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return row


async def _observation(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    observation_id: UUID,
) -> RepairObservation:
    row = await session.scalar(
        select(RepairObservation).where(
            RepairObservation.id == observation_id,
            RepairObservation.user_id == user_id,
            RepairObservation.session_id == session_id,
        )
    )
    if row is None:
        raise PartGraphError(
            code=ErrorCode.OBSERVATION_NOT_FOUND,
            message="Observation not found in this repair session.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return row


async def _photo(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    photo_id: UUID,
    include_deleted: bool = False,
) -> RepairPhotoEvidence:
    statement = select(RepairPhotoEvidence).where(
        RepairPhotoEvidence.id == photo_id,
        RepairPhotoEvidence.user_id == user_id,
        RepairPhotoEvidence.session_id == session_id,
    )
    if not include_deleted:
        statement = statement.where(RepairPhotoEvidence.deleted_at.is_(None))
    row = await session.scalar(statement)
    if row is None:
        raise PartGraphError(
            code=ErrorCode.PHOTO_EVIDENCE_NOT_FOUND,
            message="Photo evidence not found in this repair session.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return row


def serialize_storage_location(row: RepairStorageLocation) -> StorageLocationRead:
    return StorageLocationRead(
        id=row.id,
        session_id=row.session_id,
        label=row.label,
        notes=row.notes,
        created_at=row.created_at,
    )


def serialize_fastener(row: RepairFastener) -> FastenerRead:
    return FastenerRead(
        id=row.id,
        session_id=row.session_id,
        kind=row.kind,
        label=row.label,
        origin=row.origin,
        position=row.position,
        physical_state=row.physical_state,
        storage_location_id=row.storage_location_id,
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def serialize_inventory_item(row: RepairInventoryItem) -> InventoryItemRead:
    return InventoryItemRead(
        id=row.id,
        session_id=row.session_id,
        name=row.name,
        quantity=row.quantity,
        procurement_state=row.procurement_state,
        reference=row.reference,
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def serialize_observation(row: RepairObservation) -> ObservationRead:
    return ObservationRead(
        id=row.id,
        session_id=row.session_id,
        category=row.category,
        text=row.text,
        source=row.source,
        review_state=row.review_state,
        fastener_id=row.fastener_id,
        created_at=row.created_at,
    )


def serialize_photo(row: RepairPhotoEvidence) -> PhotoEvidenceRead:
    return PhotoEvidenceRead(
        id=row.id,
        session_id=row.session_id,
        purpose=row.purpose,
        observation_id=row.observation_id,
        fastener_id=row.fastener_id,
        original_filename=row.original_filename,
        media_type=row.media_type,
        byte_size=row.byte_size,
        sha256=row.sha256,
        content_url=f"/api/v1/repair-sessions/{row.session_id}/photos/{row.id}/content",
        created_at=row.created_at,
    )


async def list_storage_locations(
    session: AsyncSession, *, user_id: UUID, session_id: UUID
) -> list[StorageLocationRead]:
    await _require_session(session, user_id=user_id, session_id=session_id)
    rows = list(
        await session.scalars(
            select(RepairStorageLocation)
            .where(
                RepairStorageLocation.user_id == user_id,
                RepairStorageLocation.session_id == session_id,
            )
            .order_by(RepairStorageLocation.created_at, RepairStorageLocation.id)
        )
    )
    return [serialize_storage_location(row) for row in rows]


async def create_storage_location(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    device_id: UUID,
    idempotency_key: str,
    payload: StorageLocationCreate,
) -> StorageLocationRead:
    request_data = payload.model_dump(mode="json")
    fingerprint = _fingerprint(request_data)
    bundle, existing = await prepare_domain_mutation(
        session,
        user_id=user_id,
        session_id=session_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        event_type="storage_location_created",
    )
    if existing is not None:
        _assert_replay(existing, fingerprint)
        row = await _storage_location(
            session,
            user_id=user_id,
            session_id=session_id,
            location_id=_payload_uuid(existing, "storage_location_id"),
        )
        return serialize_storage_location(row)

    row = RepairStorageLocation(
        id=uuid4(),
        user_id=user_id,
        session_id=session_id,
        label=payload.label,
        notes=payload.notes,
    )
    session.add(row)
    await session.flush()
    await append_domain_event(
        session,
        bundle=bundle,
        user_id=user_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        event_type="storage_location_created",
        payload={
            "storage_location_id": str(row.id),
            "label": row.label,
            "request_fingerprint": fingerprint,
        },
    )
    return serialize_storage_location(row)


async def list_fasteners(
    session: AsyncSession, *, user_id: UUID, session_id: UUID
) -> list[FastenerRead]:
    await _require_session(session, user_id=user_id, session_id=session_id)
    rows = list(
        await session.scalars(
            select(RepairFastener)
            .where(RepairFastener.user_id == user_id, RepairFastener.session_id == session_id)
            .order_by(RepairFastener.created_at, RepairFastener.id)
        )
    )
    return [serialize_fastener(row) for row in rows]


async def create_fastener(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    device_id: UUID,
    idempotency_key: str,
    payload: FastenerCreate,
) -> FastenerRead:
    request_data = payload.model_dump(mode="json")
    fingerprint = _fingerprint(request_data)
    bundle, existing = await prepare_domain_mutation(
        session,
        user_id=user_id,
        session_id=session_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        event_type="fastener_recorded",
    )
    if existing is not None:
        _assert_replay(existing, fingerprint)
        return serialize_fastener(
            await _fastener(
                session,
                user_id=user_id,
                session_id=session_id,
                fastener_id=_payload_uuid(existing, "fastener_id"),
            )
        )
    if payload.storage_location_id is not None:
        await _storage_location(
            session,
            user_id=user_id,
            session_id=session_id,
            location_id=payload.storage_location_id,
        )
    row = RepairFastener(
        id=uuid4(),
        user_id=user_id,
        session_id=session_id,
        kind=payload.kind,
        label=payload.label,
        origin=payload.origin,
        position=payload.position,
        physical_state=payload.physical_state,
        storage_location_id=payload.storage_location_id,
        notes=payload.notes,
    )
    session.add(row)
    await session.flush()
    await append_domain_event(
        session,
        bundle=bundle,
        user_id=user_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        event_type="fastener_recorded",
        payload={
            "fastener_id": str(row.id),
            "kind": row.kind,
            "physical_state": row.physical_state,
            "request_fingerprint": fingerprint,
        },
    )
    return serialize_fastener(row)


async def update_fastener_state(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    fastener_id: UUID,
    device_id: UUID,
    idempotency_key: str,
    payload: FastenerStateUpdate,
) -> FastenerRead:
    request_data = {"fastener_id": str(fastener_id), **payload.model_dump(mode="json")}
    fingerprint = _fingerprint(request_data)
    bundle, existing = await prepare_domain_mutation(
        session,
        user_id=user_id,
        session_id=session_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        event_type="fastener_state_changed",
    )
    if existing is not None:
        _assert_replay(existing, fingerprint)
        return serialize_fastener(
            await _fastener(
                session,
                user_id=user_id,
                session_id=session_id,
                fastener_id=_payload_uuid(existing, "fastener_id"),
            )
        )
    row = await _fastener(
        session,
        user_id=user_id,
        session_id=session_id,
        fastener_id=fastener_id,
    )
    if payload.storage_location_id is not None:
        await _storage_location(
            session,
            user_id=user_id,
            session_id=session_id,
            location_id=payload.storage_location_id,
        )
    row.physical_state = payload.physical_state
    row.storage_location_id = payload.storage_location_id
    row.notes = payload.notes
    row.updated_at = datetime.now(UTC)
    await session.flush()
    await append_domain_event(
        session,
        bundle=bundle,
        user_id=user_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        event_type="fastener_state_changed",
        payload={
            "fastener_id": str(row.id),
            "physical_state": row.physical_state,
            "storage_location_id": str(row.storage_location_id) if row.storage_location_id else None,
            "request_fingerprint": fingerprint,
        },
    )
    return serialize_fastener(row)


async def list_inventory(
    session: AsyncSession, *, user_id: UUID, session_id: UUID
) -> list[InventoryItemRead]:
    await _require_session(session, user_id=user_id, session_id=session_id)
    rows = list(
        await session.scalars(
            select(RepairInventoryItem)
            .where(
                RepairInventoryItem.user_id == user_id,
                RepairInventoryItem.session_id == session_id,
            )
            .order_by(RepairInventoryItem.created_at, RepairInventoryItem.id)
        )
    )
    return [serialize_inventory_item(row) for row in rows]


async def create_inventory_item(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    device_id: UUID,
    idempotency_key: str,
    payload: InventoryItemCreate,
) -> InventoryItemRead:
    request_data = payload.model_dump(mode="json")
    fingerprint = _fingerprint(request_data)
    bundle, existing = await prepare_domain_mutation(
        session,
        user_id=user_id,
        session_id=session_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        event_type="inventory_item_recorded",
    )
    if existing is not None:
        _assert_replay(existing, fingerprint)
        return serialize_inventory_item(
            await _inventory_item(
                session,
                user_id=user_id,
                session_id=session_id,
                item_id=_payload_uuid(existing, "inventory_item_id"),
            )
        )
    row = RepairInventoryItem(
        id=uuid4(),
        user_id=user_id,
        session_id=session_id,
        name=payload.name,
        quantity=payload.quantity,
        procurement_state=payload.procurement_state,
        reference=payload.reference,
        notes=payload.notes,
    )
    session.add(row)
    await session.flush()
    await append_domain_event(
        session,
        bundle=bundle,
        user_id=user_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        event_type="inventory_item_recorded",
        payload={
            "inventory_item_id": str(row.id),
            "procurement_state": row.procurement_state,
            "request_fingerprint": fingerprint,
        },
    )
    return serialize_inventory_item(row)


async def update_inventory_state(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    item_id: UUID,
    device_id: UUID,
    idempotency_key: str,
    payload: InventoryStateUpdate,
) -> InventoryItemRead:
    request_data = {"inventory_item_id": str(item_id), **payload.model_dump(mode="json")}
    fingerprint = _fingerprint(request_data)
    bundle, existing = await prepare_domain_mutation(
        session,
        user_id=user_id,
        session_id=session_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        event_type="inventory_state_changed",
    )
    if existing is not None:
        _assert_replay(existing, fingerprint)
        return serialize_inventory_item(
            await _inventory_item(
                session,
                user_id=user_id,
                session_id=session_id,
                item_id=_payload_uuid(existing, "inventory_item_id"),
            )
        )
    row = await _inventory_item(
        session,
        user_id=user_id,
        session_id=session_id,
        item_id=item_id,
    )
    row.procurement_state = payload.procurement_state
    if payload.quantity is not None:
        row.quantity = payload.quantity
    row.notes = payload.notes
    row.updated_at = datetime.now(UTC)
    await session.flush()
    await append_domain_event(
        session,
        bundle=bundle,
        user_id=user_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        event_type="inventory_state_changed",
        payload={
            "inventory_item_id": str(row.id),
            "procurement_state": row.procurement_state,
            "quantity": row.quantity,
            "request_fingerprint": fingerprint,
        },
    )
    return serialize_inventory_item(row)


async def list_observations(
    session: AsyncSession, *, user_id: UUID, session_id: UUID
) -> list[ObservationRead]:
    await _require_session(session, user_id=user_id, session_id=session_id)
    rows = list(
        await session.scalars(
            select(RepairObservation)
            .where(
                RepairObservation.user_id == user_id,
                RepairObservation.session_id == session_id,
            )
            .order_by(RepairObservation.created_at, RepairObservation.id)
        )
    )
    return [serialize_observation(row) for row in rows]


async def create_observation(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    device_id: UUID,
    idempotency_key: str,
    payload: ObservationCreate,
) -> ObservationRead:
    request_data = payload.model_dump(mode="json")
    fingerprint = _fingerprint(request_data)
    bundle, existing = await prepare_domain_mutation(
        session,
        user_id=user_id,
        session_id=session_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        event_type="observation_recorded",
    )
    if existing is not None:
        _assert_replay(existing, fingerprint)
        return serialize_observation(
            await _observation(
                session,
                user_id=user_id,
                session_id=session_id,
                observation_id=_payload_uuid(existing, "observation_id"),
            )
        )
    if payload.fastener_id is not None:
        await _fastener(
            session,
            user_id=user_id,
            session_id=session_id,
            fastener_id=payload.fastener_id,
        )
    row = RepairObservation(
        id=uuid4(),
        user_id=user_id,
        session_id=session_id,
        category=payload.category,
        text=payload.text,
        source="user",
        review_state="confirmed",
        fastener_id=payload.fastener_id,
    )
    session.add(row)
    await session.flush()
    await append_domain_event(
        session,
        bundle=bundle,
        user_id=user_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        event_type="observation_recorded",
        payload={
            "observation_id": str(row.id),
            "category": row.category,
            "source": row.source,
            "review_state": row.review_state,
            "request_fingerprint": fingerprint,
        },
    )
    return serialize_observation(row)


async def list_photos(
    session: AsyncSession, *, user_id: UUID, session_id: UUID
) -> list[PhotoEvidenceRead]:
    await _require_session(session, user_id=user_id, session_id=session_id)
    rows = list(
        await session.scalars(
            select(RepairPhotoEvidence)
            .where(
                RepairPhotoEvidence.user_id == user_id,
                RepairPhotoEvidence.session_id == session_id,
                RepairPhotoEvidence.deleted_at.is_(None),
            )
            .order_by(RepairPhotoEvidence.created_at, RepairPhotoEvidence.id)
        )
    )
    return [serialize_photo(row) for row in rows]


async def create_photo(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    device_id: UUID,
    idempotency_key: str,
    purpose: PhotoPurpose,
    observation_id: UUID | None,
    fastener_id: UUID | None,
    filename: str | None,
    data: bytes,
    maximum_bytes: int,
) -> PhotoEvidenceRead:
    if not data or len(data) > maximum_bytes:
        raise PartGraphError(
            code=ErrorCode.PHOTO_TOO_LARGE,
            message=f"Photo must be between 1 byte and {maximum_bytes} bytes.",
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        )
    try:
        media_type, extension = detect_photo_media_type(data)
    except PhotoFormatError as exc:
        raise PartGraphError(
            code=ErrorCode.PHOTO_MEDIA_TYPE_UNSUPPORTED,
            message="Photo content must be JPEG, PNG, WebP, or HEIC.",
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        ) from exc
    if purpose == "fastener" and fastener_id is None:
        raise PartGraphError(
            code=ErrorCode.PHOTO_ATTACHMENT_INVALID,
            message="Fastener photo evidence requires a fastener_id.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    if observation_id is not None:
        await _observation(
            session,
            user_id=user_id,
            session_id=session_id,
            observation_id=observation_id,
        )
    if fastener_id is not None:
        await _fastener(
            session,
            user_id=user_id,
            session_id=session_id,
            fastener_id=fastener_id,
        )

    digest = hashlib.sha256(data).hexdigest()
    request_data = {
        "purpose": purpose,
        "observation_id": str(observation_id) if observation_id else None,
        "fastener_id": str(fastener_id) if fastener_id else None,
        "sha256": digest,
    }
    fingerprint = _fingerprint(request_data)
    bundle, existing = await prepare_domain_mutation(
        session,
        user_id=user_id,
        session_id=session_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        event_type="photo_evidence_added",
    )
    if existing is not None:
        _assert_replay(existing, fingerprint)
        return serialize_photo(
            await _photo(
                session,
                user_id=user_id,
                session_id=session_id,
                photo_id=_payload_uuid(existing, "photo_id"),
            )
        )

    photo_id = uuid4()
    storage_key = new_storage_key(photo_id, extension)
    await store_photo(storage_key, data)
    try:
        row = RepairPhotoEvidence(
            id=photo_id,
            user_id=user_id,
            session_id=session_id,
            purpose=purpose,
            observation_id=observation_id,
            fastener_id=fastener_id,
            storage_key=storage_key,
            original_filename=_clean_filename(filename),
            media_type=media_type,
            byte_size=len(data),
            sha256=digest,
        )
        session.add(row)
        await session.flush()
        await append_domain_event(
            session,
            bundle=bundle,
            user_id=user_id,
            device_id=device_id,
            idempotency_key=idempotency_key,
            event_type="photo_evidence_added",
            payload={
                "photo_id": str(row.id),
                "purpose": row.purpose,
                "sha256": row.sha256,
                "request_fingerprint": fingerprint,
            },
        )
    except Exception:
        await delete_photo_file(storage_key)
        raise
    return serialize_photo(row)


async def photo_content(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    photo_id: UUID,
) -> tuple[RepairPhotoEvidence, Path]:
    row = await _photo(
        session,
        user_id=user_id,
        session_id=session_id,
        photo_id=photo_id,
    )
    return row, photo_path(row.storage_key)


async def delete_photo(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    photo_id: UUID,
    device_id: UUID,
    idempotency_key: str,
) -> PhotoDeleteRead:
    request_data = {"photo_id": str(photo_id)}
    fingerprint = _fingerprint(request_data)
    bundle, existing = await prepare_domain_mutation(
        session,
        user_id=user_id,
        session_id=session_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        event_type="photo_evidence_deleted",
    )
    if existing is not None:
        _assert_replay(existing, fingerprint)
        row = await _photo(
            session,
            user_id=user_id,
            session_id=session_id,
            photo_id=_payload_uuid(existing, "photo_id"),
            include_deleted=True,
        )
        if row.deleted_at is None:
            raise PartGraphError(
                code=ErrorCode.REPAIR_SESSION_STATE_CORRUPT,
                message="Photo deletion event exists without a deleted photo state.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return PhotoDeleteRead(id=row.id, deleted_at=row.deleted_at)

    row = await _photo(
        session,
        user_id=user_id,
        session_id=session_id,
        photo_id=photo_id,
    )
    await delete_photo_file(row.storage_key)
    row.deleted_at = datetime.now(UTC)
    await session.flush()
    await append_domain_event(
        session,
        bundle=bundle,
        user_id=user_id,
        device_id=device_id,
        idempotency_key=idempotency_key,
        event_type="photo_evidence_deleted",
        payload={
            "photo_id": str(row.id),
            "request_fingerprint": fingerprint,
        },
    )
    return PhotoDeleteRead(id=row.id, deleted_at=row.deleted_at)
