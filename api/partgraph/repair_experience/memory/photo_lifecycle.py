from __future__ import annotations

import hashlib
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from partgraph.database import session_factory

from ..errors import ErrorCode, PartGraphError
from ..repair_session.service import append_domain_event, prepare_domain_mutation
from .models import RepairPhotoEvidence
from .schemas import PhotoDeleteRead, PhotoEvidenceRead, PhotoPurpose
from .service import (
    _assert_replay,
    _clean_filename,
    _fastener,
    _fingerprint,
    _observation,
    _payload_uuid,
    _photo,
    serialize_photo,
)
from .storage import (
    PhotoFormatError,
    delete_photo_file,
    detect_photo_media_type,
    new_storage_key,
    photo_path,
    store_photo,
)

MEDIA_WORKER_ROLE = "partgraph_media_worker"
_PENDING_STATES = ("pending_upload", "delete_pending")


def cron_request_authorized(authorization: str | None) -> bool:
    secret = os.getenv("CRON_SECRET", "").strip()
    if not secret or authorization is None:
        return False
    return secrets.compare_digest(authorization, f"Bearer {secret}")


def _storage_error_label(exc: Exception) -> str:
    if isinstance(exc, PartGraphError):
        code = getattr(exc.code, "value", exc.code)
        return str(code)[:128]
    return type(exc).__name__[:128]


async def _assume_media_worker(session: AsyncSession) -> None:
    await session.execute(text(f"SET LOCAL ROLE {MEDIA_WORKER_ROLE}"))


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
    """Record durable upload intent without touching external storage before commit."""

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
    row = RepairPhotoEvidence(
        id=photo_id,
        user_id=user_id,
        session_id=session_id,
        purpose=purpose,
        observation_id=observation_id,
        fastener_id=fastener_id,
        storage_key=new_storage_key(photo_id, extension),
        original_filename=_clean_filename(filename),
        media_type=media_type,
        byte_size=len(data),
        sha256=digest,
        storage_state="pending_upload",
        pending_content=data,
        storage_attempts=0,
        storage_error=None,
        storage_updated_at=datetime.now(UTC),
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
    return serialize_photo(row)


async def delete_photo(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    photo_id: UUID,
    device_id: UUID,
    idempotency_key: str,
) -> PhotoDeleteRead:
    """Commit the tombstone before external deletion is attempted."""

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
    row.deleted_at = datetime.now(UTC)
    row.storage_state = "delete_pending"
    row.pending_content = None
    row.storage_error = None
    row.storage_updated_at = datetime.now(UTC)
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


async def reconcile_photo_storage_row(
    session: AsyncSession,
    row: RepairPhotoEvidence,
) -> str:
    """Apply one idempotent storage side effect while the durable row is locked."""

    state = row.storage_state
    if state not in _PENDING_STATES:
        return state

    row.storage_attempts += 1
    row.storage_updated_at = datetime.now(UTC)
    try:
        if state == "pending_upload":
            if row.pending_content is None:
                raise PartGraphError(
                    code=ErrorCode.REPAIR_SESSION_STATE_CORRUPT,
                    message="Pending photo upload has no durable content payload.",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            await store_photo(row.storage_key, bytes(row.pending_content))
            row.pending_content = None
            row.storage_state = "ready"
        else:
            await delete_photo_file(row.storage_key)
            row.storage_state = "deleted"
        row.storage_error = None
        result = row.storage_state
    except Exception as exc:
        row.storage_error = _storage_error_label(exc)
        result = "failed"

    await session.flush()
    return result


async def reconcile_photo_storage_item(photo_id: UUID) -> str:
    """Reconcile one photo in its own transaction so retries survive process loss."""

    async with session_factory() as session:
        async with session.begin():
            await _assume_media_worker(session)
            row = await session.scalar(
                select(RepairPhotoEvidence)
                .where(RepairPhotoEvidence.id == photo_id)
                .with_for_update()
            )
            if row is None:
                return "missing"
            return await reconcile_photo_storage_row(session, row)


async def reconcile_photo_storage_batch(*, limit: int = 20) -> dict[str, int]:
    """Reconcile durable pending work; safe to invoke repeatedly or concurrently."""

    bounded_limit = max(1, min(limit, 100))
    async with session_factory() as session:
        async with session.begin():
            await _assume_media_worker(session)
            pending_ids = list(
                await session.scalars(
                    select(RepairPhotoEvidence.id)
                    .where(RepairPhotoEvidence.storage_state.in_(_PENDING_STATES))
                    .order_by(
                        RepairPhotoEvidence.storage_updated_at,
                        RepairPhotoEvidence.id,
                    )
                    .limit(bounded_limit)
                )
            )

    counts = {"ready": 0, "deleted": 0, "failed": 0, "noop": 0}
    for photo_id in pending_ids:
        result = await reconcile_photo_storage_item(photo_id)
        if result in counts:
            counts[result] += 1
        else:
            counts["noop"] += 1
    return counts


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
    if row.storage_state == "pending_upload":
        await reconcile_photo_storage_item(row.id)
        await session.refresh(
            row,
            attribute_names=[
                "storage_state",
                "pending_content",
                "storage_attempts",
                "storage_error",
                "storage_updated_at",
            ],
        )
    if row.storage_state != "ready":
        raise PartGraphError(
            code=ErrorCode.PHOTO_CONTENT_UNAVAILABLE,
            message="Photo content is still being finalized. Try again shortly.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            retryable=True,
            headers={"Retry-After": "1"},
        )
    return row, photo_path(row.storage_key)
