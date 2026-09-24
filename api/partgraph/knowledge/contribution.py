from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from ..errors import ErrorCode, ErrorEnvelope, PartGraphError
from ..identity.auth.dependencies import AuthSessionDep, require_csrf
from ..identity.auth.roles import ContributorUserDep, assume_contributor_database_role
from ..identity.vehicle.models import VehicleConfiguration
from .models import CatalogIngestionBatch, CatalogSource, CatalogSourceRecord

ClaimDomainValue = Literal[
    "vehicle_identity",
    "safety_campaign",
    "repair_requirement",
    "repair_procedure",
    "part_fitment",
]
ClaimRiskValue = Literal["normal", "safety_critical"]
EXTRACTION_METHOD = "human_structured_submission_v1"


class MechanicalClaimCandidateCreate(BaseModel):
    source_key: str = Field(min_length=1, max_length=96, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    source_record_id: str = Field(min_length=1, max_length=256)
    source_url: str = Field(min_length=1, max_length=2048)
    raw_payload: dict[str, object]
    claim_domain: ClaimDomainValue
    claim_risk: ClaimRiskValue = "normal"
    normalized_key: str = Field(min_length=1, max_length=160)
    claim_payload: dict[str, object]
    explicit_claim: bool
    exact_applicability: bool
    vehicle_configuration_id: UUID | None = None
    repair_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    )
    observed_at: datetime | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    provenance_note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_scope(self) -> MechanicalClaimCandidateCreate:
        if not self.raw_payload:
            raise ValueError("raw_payload must contain the captured source evidence")
        if not self.claim_payload:
            raise ValueError("claim_payload must contain the proposed mechanical fact")
        if self.exact_applicability and self.vehicle_configuration_id is None:
            raise ValueError(
                "vehicle_configuration_id is required when exact_applicability is true"
            )
        if self.claim_domain in {"repair_requirement", "repair_procedure"} and not self.repair_key:
            raise ValueError("repair_key is required for repair requirement/procedure candidates")
        if self.claim_domain not in {"repair_requirement", "repair_procedure"} and self.repair_key:
            raise ValueError("repair_key is only valid for repair requirement/procedure candidates")
        return self


class MechanicalClaimCandidateRead(BaseModel):
    staging_record_id: UUID
    ingestion_batch_id: UUID
    source_key: str
    source_class: str
    review_status: Literal["pending"] = "pending"
    raw_sha256: str
    dedupe_key: str


router = APIRouter(
    prefix="/api/v1/contributions",
    tags=["Knowledge Contributions"],
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


def _stable_json_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _candidate_dedupe_key(
    *,
    source_key: str,
    source_record_id: str,
    raw_sha256: str,
    claim_domain: str,
    normalized_key: str,
    vehicle_configuration_id: UUID | None,
    repair_key: str | None,
) -> str:
    identity = "\x1f".join(
        (
            source_key.casefold(),
            source_record_id.casefold(),
            raw_sha256,
            claim_domain,
            normalized_key.casefold(),
            str(vehicle_configuration_id or ""),
            repair_key or "",
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _vehicle_snapshot(configuration: VehicleConfiguration | None) -> dict[str, object] | None:
    if configuration is None:
        return None
    return {
        "vehicle_configuration_id": str(configuration.id),
        "year": configuration.year,
        "market": configuration.market,
        "make": configuration.make,
        "model": configuration.model,
        "generation": configuration.generation,
        "trim": configuration.trim,
        "body_style": configuration.body_style,
        "engine": configuration.engine,
        "transmission": configuration.transmission,
        "drivetrain": configuration.drivetrain,
    }


@router.post(
    "/mechanical-claims",
    response_model=MechanicalClaimCandidateRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[CsrfDep],
)
async def submit_mechanical_claim_candidate(
    request: MechanicalClaimCandidateCreate,
    user: ContributorUserDep,
    db: AuthSessionDep,
) -> MechanicalClaimCandidateRead:
    await assume_contributor_database_role(db)

    source = await db.scalar(
        select(CatalogSource).where(CatalogSource.source_key == request.source_key)
    )
    if source is None:
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_SOURCE_NOT_FOUND,
            message="The selected evidence source is not registered.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if source.license_status == "prohibited":
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_SOURCE_PROHIBITED,
            message="This source is prohibited for PartGraph evidence submission.",
            status_code=status.HTTP_409_CONFLICT,
        )

    configuration: VehicleConfiguration | None = None
    if request.vehicle_configuration_id is not None:
        configuration = await db.get(VehicleConfiguration, request.vehicle_configuration_id)
        if configuration is None:
            raise PartGraphError(
                code=ErrorCode.KNOWLEDGE_CANDIDATE_INVALID,
                message="The candidate references an unknown vehicle configuration.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

    raw_sha256 = _stable_json_hash(request.raw_payload)
    dedupe_key = _candidate_dedupe_key(
        source_key=source.source_key,
        source_record_id=request.source_record_id,
        raw_sha256=raw_sha256,
        claim_domain=request.claim_domain,
        normalized_key=request.normalized_key,
        vehicle_configuration_id=request.vehicle_configuration_id,
        repair_key=request.repair_key,
    )
    batch_id = uuid5(NAMESPACE_URL, f"partgraph:contribution:batch:{dedupe_key}")
    record_id = uuid5(NAMESPACE_URL, f"partgraph:contribution:record:{dedupe_key}")
    now = datetime.now(UTC)

    candidate_payload: dict[str, object] = {
        "mechanical_claim": {
            "claim_domain": request.claim_domain,
            "claim_risk": request.claim_risk,
            "normalized_key": request.normalized_key,
            "claim_payload": request.claim_payload,
            "explicit_claim": request.explicit_claim,
            "exact_applicability": request.exact_applicability,
            "vehicle_configuration_id": (
                str(request.vehicle_configuration_id)
                if request.vehicle_configuration_id is not None
                else None
            ),
            "repair_key": request.repair_key,
        }
    }
    provenance: dict[str, object] = {
        "submission_kind": "human_contributor",
        "submitted_by_user_id": str(user.id),
        "submitted_by_role": user.role,
        "source_registry_id": str(source.id),
        "source_license_status_at_submission": source.license_status,
    }
    if request.provenance_note:
        provenance["note"] = request.provenance_note

    await db.execute(
        insert(CatalogIngestionBatch)
        .values(
            id=batch_id,
            source_name=source.source_key,
            source_type=source.source_class,
            collector_version="contributor-api-v1",
            status="completed",
            started_at=now,
            completed_at=now,
            created_at=now,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    await db.execute(
        insert(CatalogSourceRecord)
        .values(
            id=record_id,
            batch_id=batch_id,
            source_record_id=request.source_record_id,
            source_url=request.source_url,
            fetched_at=now,
            observed_at=request.observed_at,
            candidate_type="mechanical_claim_candidate",
            raw_sha256=raw_sha256,
            raw_payload=request.raw_payload,
            candidate_payload=candidate_payload,
            vehicle_identity=_vehicle_snapshot(configuration),
            provenance=provenance,
            extraction_method=EXTRACTION_METHOD,
            confidence=request.confidence,
            review_status="pending",
            dedupe_key=dedupe_key,
            created_at=now,
        )
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
    )

    return MechanicalClaimCandidateRead(
        staging_record_id=record_id,
        ingestion_batch_id=batch_id,
        source_key=source.source_key,
        source_class=source.source_class,
        raw_sha256=raw_sha256,
        dedupe_key=dedupe_key,
    )
