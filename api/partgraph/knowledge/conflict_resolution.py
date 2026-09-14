from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from ..errors import ErrorCode, ErrorEnvelope, PartGraphError
from ..identity.auth.dependencies import AuthSessionDep, require_csrf
from ..identity.auth.roles import CuratorUserDep, assume_curator_database_role
from .models import MechanicalClaim
from .provenance import CanonicalConflict, CanonicalConflictItem

ConflictResolutionValue = Literal[
    "accepted_evidence",
    "superseded",
    "duplicate",
    "insufficient_evidence",
    "not_applicable",
]
_SELECTED_RESOLUTIONS = frozenset({"accepted_evidence", "superseded", "duplicate"})


class CanonicalConflictResolutionCreate(BaseModel):
    resolution: ConflictResolutionValue
    selected_claim_id: UUID | None = None
    rationale: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_selection(self) -> CanonicalConflictResolutionCreate:
        self.rationale = " ".join(self.rationale.split())
        requires_selection = self.resolution in _SELECTED_RESOLUTIONS
        if requires_selection and self.selected_claim_id is None:
            raise ValueError("selected_claim_id is required for this resolution")
        if not requires_selection and self.selected_claim_id is not None:
            raise ValueError("selected_claim_id is not valid for this resolution")
        return self


class CanonicalConflictResolutionRead(BaseModel):
    conflict_id: UUID
    conflict_key: str
    canonical_domain: str
    conflict_state: Literal["resolved"] = "resolved"
    resolution: ConflictResolutionValue
    selected_claim_id: UUID | None
    affected_claim_ids: list[UUID]
    resolved_by: str
    resolved_at: datetime
    idempotent: bool = False


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


def _actor(user: CuratorUserDep) -> str:
    return f"{user.id}:{user.role}"


def _invalid(message: str) -> PartGraphError:
    return PartGraphError(
        code=ErrorCode.KNOWLEDGE_CONFLICT_RESOLUTION_INVALID,
        message=message,
        status_code=status.HTTP_409_CONFLICT,
    )


def _selected_item_id(items: list[CanonicalConflictItem]) -> UUID | None:
    selected = [
        item.mechanical_claim_id
        for item in items
        if item.disposition == "selected" and item.mechanical_claim_id is not None
    ]
    if len(selected) > 1:
        raise _invalid("Resolved conflict contains multiple selected claims.")
    return selected[0] if selected else None


@router.post(
    "/conflicts/{conflict_id}/resolve",
    response_model=CanonicalConflictResolutionRead,
    dependencies=[CsrfDep],
)
async def resolve_canonical_conflict(
    conflict_id: UUID,
    request: CanonicalConflictResolutionCreate,
    user: CuratorUserDep,
    db: AuthSessionDep,
) -> CanonicalConflictResolutionRead:
    await assume_curator_database_role(db)
    actor = _actor(user)

    conflict = (
        await db.execute(
            select(CanonicalConflict)
            .where(CanonicalConflict.id == conflict_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if conflict is None:
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_CONFLICT_NOT_FOUND,
            message="Canonical conflict not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    items = list(
        await db.scalars(
            select(CanonicalConflictItem)
            .where(CanonicalConflictItem.conflict_id == conflict.id)
            .order_by(CanonicalConflictItem.created_at, CanonicalConflictItem.id)
            .with_for_update()
        )
    )
    if not items:
        raise _invalid("Canonical conflict has no contenders.")
    if any(item.record_evidence_id is not None for item in items):
        raise _invalid(
            "This conflict contains publication-evidence contenders and cannot be "
            "resolved by the mechanical-claim resolver."
        )

    claim_ids = [
        item.mechanical_claim_id
        for item in items
        if item.mechanical_claim_id is not None
    ]
    if len(claim_ids) != len(items):
        raise _invalid("Canonical conflict contains an invalid contender reference.")

    claims = list(
        await db.scalars(
            select(MechanicalClaim)
            .where(MechanicalClaim.id.in_(claim_ids))
            .with_for_update()
        )
    )
    claim_by_id = {claim.id: claim for claim in claims}
    if len(claim_by_id) != len(set(claim_ids)):
        raise _invalid("Canonical conflict references a missing mechanical claim.")
    if any(claim.conflict_key != conflict.conflict_key for claim in claims):
        raise _invalid("Canonical conflict contains a claim from a different conflict scope.")

    if conflict.conflict_state == "resolved":
        selected_claim_id = _selected_item_id(items)
        if (
            conflict.resolution == request.resolution
            and selected_claim_id == request.selected_claim_id
            and conflict.resolved_at is not None
            and conflict.resolved_by is not None
        ):
            return CanonicalConflictResolutionRead(
                conflict_id=conflict.id,
                conflict_key=conflict.conflict_key,
                canonical_domain=conflict.canonical_domain,
                resolution=request.resolution,
                selected_claim_id=selected_claim_id,
                affected_claim_ids=sorted(set(claim_ids), key=str),
                resolved_by=conflict.resolved_by,
                resolved_at=conflict.resolved_at,
                idempotent=True,
            )
        raise _invalid("Canonical conflict is already resolved differently.")

    active_items = [
        item
        for item in items
        if item.disposition == "contender"
        or claim_by_id[item.mechanical_claim_id].promotion_state == "conflict"
    ]
    if not active_items:
        raise _invalid("Canonical conflict has no active claim contenders.")
    active_claim_ids = {
        item.mechanical_claim_id
        for item in active_items
        if item.mechanical_claim_id is not None
    }

    selected_claim: MechanicalClaim | None = None
    if request.selected_claim_id is not None:
        if request.selected_claim_id not in active_claim_ids:
            raise _invalid("Selected claim is not an active contender in this conflict.")
        selected_claim = claim_by_id[request.selected_claim_id]

    now = datetime.now(UTC)
    for item in active_items:
        claim_id = item.mechanical_claim_id
        if claim_id is None:
            raise _invalid("Canonical conflict contains an invalid claim contender.")
        claim = claim_by_id[claim_id]
        claim.reviewed_at = now
        claim.reviewed_by = actor

        if selected_claim is not None and claim.id == selected_claim.id:
            claim.promotion_state = "verified"
            claim.superseded_by_id = None
            item.disposition = "selected"
            continue

        if request.resolution in {"superseded", "duplicate"} and selected_claim is not None:
            claim.promotion_state = "superseded"
            claim.superseded_by_id = selected_claim.id
            item.disposition = "superseded"
        else:
            claim.promotion_state = "rejected"
            claim.superseded_by_id = None
            item.disposition = "rejected"

    conflict.conflict_state = "resolved"
    conflict.resolution = request.resolution
    conflict.resolution_rationale = request.rationale
    conflict.resolved_at = now
    conflict.resolved_by = actor
    await db.flush()

    return CanonicalConflictResolutionRead(
        conflict_id=conflict.id,
        conflict_key=conflict.conflict_key,
        canonical_domain=conflict.canonical_domain,
        resolution=request.resolution,
        selected_claim_id=selected_claim.id if selected_claim is not None else None,
        affected_claim_ids=sorted(active_claim_ids, key=str),
        resolved_by=actor,
        resolved_at=now,
    )
