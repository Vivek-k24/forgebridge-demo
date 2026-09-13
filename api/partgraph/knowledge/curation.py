from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy import select, text

from ..errors import ErrorCode, ErrorEnvelope, PartGraphError
from ..identity.auth.dependencies import AuthSessionDep, require_csrf
from ..identity.auth.roles import ReviewerUserDep
from .models import CatalogIngestionBatch, CatalogSourceRecord, CatalogVerifiedEvidence
from .staging import CatalogStagingError, promote_verified_record, reject_staging_record

ReviewStatus = Literal["pending", "verified", "rejected"]
REVIEWER_DATABASE_ROLE = "partgraph_reviewer"


class CurationRecordSummaryRead(BaseModel):
    id: UUID
    batch_id: UUID
    source_name: str
    source_type: str
    source_record_id: str
    source_url: str
    candidate_type: str
    extraction_method: str
    confidence: Decimal | None
    review_status: ReviewStatus
    raw_sha256: str
    fetched_at: datetime
    observed_at: datetime | None
    reviewed_at: datetime | None
    reviewed_by: str | None
    created_at: datetime


class CurationRecordDetailRead(CurationRecordSummaryRead):
    raw_payload: dict[str, object]
    candidate_payload: dict[str, object]
    vehicle_identity: dict[str, object] | None
    provenance: dict[str, object]


class CurationReviewRead(BaseModel):
    record_id: UUID
    review_status: ReviewStatus
    reviewed_by: str
    reviewed_at: datetime | None
    verified_evidence_id: UUID | None = None
    newly_verified: bool = False


router = APIRouter(
    prefix="/api/v1/curation",
    tags=["Knowledge Curation"],
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


async def _assume_reviewer_database_role(db: AuthSessionDep) -> None:
    await db.execute(text(f"SET LOCAL ROLE {REVIEWER_DATABASE_ROLE}"))


def _actor(user: ReviewerUserDep) -> str:
    return f"{user.id}:{user.role}"


def _summary(
    record: CatalogSourceRecord,
    batch: CatalogIngestionBatch,
) -> CurationRecordSummaryRead:
    return CurationRecordSummaryRead(
        id=record.id,
        batch_id=record.batch_id,
        source_name=batch.source_name,
        source_type=batch.source_type,
        source_record_id=record.source_record_id,
        source_url=record.source_url,
        candidate_type=record.candidate_type,
        extraction_method=record.extraction_method,
        confidence=record.confidence,
        review_status=record.review_status,
        raw_sha256=record.raw_sha256,
        fetched_at=record.fetched_at,
        observed_at=record.observed_at,
        reviewed_at=record.reviewed_at,
        reviewed_by=record.reviewed_by,
        created_at=record.created_at,
    )


def _detail(
    record: CatalogSourceRecord,
    batch: CatalogIngestionBatch,
) -> CurationRecordDetailRead:
    return CurationRecordDetailRead(
        **_summary(record, batch).model_dump(),
        raw_payload=record.raw_payload,
        candidate_payload=record.candidate_payload,
        vehicle_identity=record.vehicle_identity,
        provenance=record.provenance,
    )


def _staging_error(exc: CatalogStagingError) -> PartGraphError:
    message = str(exc)
    if "does not exist" in message:
        return PartGraphError(
            code=ErrorCode.CURATION_RECORD_NOT_FOUND,
            message="Curation record not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return PartGraphError(
        code=ErrorCode.CURATION_REVIEW_CONFLICT,
        message=message,
        status_code=status.HTTP_409_CONFLICT,
    )


async def _record_with_batch(
    db: AuthSessionDep,
    record_id: UUID,
) -> tuple[CatalogSourceRecord, CatalogIngestionBatch]:
    row = (
        await db.execute(
            select(CatalogSourceRecord, CatalogIngestionBatch)
            .join(CatalogIngestionBatch, CatalogIngestionBatch.id == CatalogSourceRecord.batch_id)
            .where(CatalogSourceRecord.id == record_id)
        )
    ).one_or_none()
    if row is None:
        raise PartGraphError(
            code=ErrorCode.CURATION_RECORD_NOT_FOUND,
            message="Curation record not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return row[0], row[1]


@router.get("/staging", response_model=list[CurationRecordSummaryRead])
async def list_staging_records(
    user: ReviewerUserDep,
    db: AuthSessionDep,
    review_status: ReviewStatus = "pending",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[CurationRecordSummaryRead]:
    del user
    await _assume_reviewer_database_role(db)
    rows = (
        await db.execute(
            select(CatalogSourceRecord, CatalogIngestionBatch)
            .join(CatalogIngestionBatch, CatalogIngestionBatch.id == CatalogSourceRecord.batch_id)
            .where(CatalogSourceRecord.review_status == review_status)
            .order_by(CatalogSourceRecord.created_at.asc(), CatalogSourceRecord.id.asc())
            .limit(limit)
        )
    ).all()
    return [_summary(record, batch) for record, batch in rows]


@router.get("/staging/{record_id}", response_model=CurationRecordDetailRead)
async def staging_record(
    record_id: UUID,
    user: ReviewerUserDep,
    db: AuthSessionDep,
) -> CurationRecordDetailRead:
    del user
    await _assume_reviewer_database_role(db)
    record, batch = await _record_with_batch(db, record_id)
    return _detail(record, batch)


@router.post(
    "/staging/{record_id}/verify",
    response_model=CurationReviewRead,
    dependencies=[CsrfDep],
)
async def verify_staging_record(
    record_id: UUID,
    user: ReviewerUserDep,
    db: AuthSessionDep,
) -> CurationReviewRead:
    await _assume_reviewer_database_role(db)
    actor = _actor(user)
    try:
        evidence, created = await promote_verified_record(
            db,
            record_id=record_id,
            reviewer=actor,
        )
    except CatalogStagingError as exc:
        raise _staging_error(exc) from exc

    record = await db.get(CatalogSourceRecord, record_id)
    if record is None:
        raise PartGraphError(
            code=ErrorCode.CURATION_RECORD_NOT_FOUND,
            message="Curation record not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return CurationReviewRead(
        record_id=record.id,
        review_status="verified",
        reviewed_by=record.reviewed_by or actor,
        reviewed_at=record.reviewed_at,
        verified_evidence_id=evidence.id,
        newly_verified=created,
    )


@router.post(
    "/staging/{record_id}/reject",
    response_model=CurationReviewRead,
    dependencies=[CsrfDep],
)
async def reject_staging_candidate(
    record_id: UUID,
    user: ReviewerUserDep,
    db: AuthSessionDep,
) -> CurationReviewRead:
    await _assume_reviewer_database_role(db)
    actor = _actor(user)
    try:
        record = await reject_staging_record(
            db,
            record_id=record_id,
            reviewer=actor,
        )
    except CatalogStagingError as exc:
        raise _staging_error(exc) from exc
    return CurationReviewRead(
        record_id=record.id,
        review_status="rejected",
        reviewed_by=record.reviewed_by or actor,
        reviewed_at=record.reviewed_at,
    )
