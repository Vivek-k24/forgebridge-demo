from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from ..identity.vehicle.models import VehicleConfiguration
from .models import CatalogSourceRecord
from .staging import (
    StageRecordInput,
    complete_ingestion_batch,
    create_ingestion_batch,
    stage_source_record,
)

ClaimDomainValue = Literal[
    "vehicle_identity",
    "safety_campaign",
    "repair_requirement",
    "repair_procedure",
    "part_fitment",
]
ClaimRiskValue = Literal["normal", "safety_critical"]
MECHANICAL_CLAIM_CAPABILITY = "mechanical_claim_candidates"
MECHANICAL_CLAIM_CANDIDATE = "mechanical_claim_candidate"


class ExtractionError(ValueError):
    pass


class ProviderMetadata(Protocol):
    id: UUID
    provider_key: str
    provider_kind: str
    enabled: bool
    capabilities: list[str]


class SourceMetadata(Protocol):
    id: UUID
    source_key: str
    source_class: str
    license_status: str
    automation_allowed: bool


@dataclass(frozen=True, slots=True)
class RawProviderRecord:
    source_record_id: str
    source_url: str
    fetched_at: datetime
    raw_payload: dict[str, object]
    provenance: dict[str, object]
    observed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ExtractedCandidate:
    candidate_type: str
    candidate_payload: dict[str, object]
    vehicle_configuration_id: UUID | None = None
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class StagedExtractionResult:
    ingestion_batch_id: UUID
    staging_record_ids: tuple[UUID, ...]
    inserted_count: int


class ExtractionAdapter(Protocol):
    adapter_key: str
    adapter_version: str
    required_capability: str
    supported_provider_kinds: frozenset[str]

    def extract(self, record: RawProviderRecord) -> tuple[ExtractedCandidate, ...]: ...


class _StructuredMechanicalClaim(BaseModel):
    claim_domain: ClaimDomainValue
    claim_risk: ClaimRiskValue = "normal"
    normalized_key: str = Field(min_length=1, max_length=160)
    claim_payload: dict[str, object]
    explicit_claim: bool
    exact_applicability: bool
    vehicle_configuration_id: UUID | None = None
    repair_key: str | None = Field(default=None, min_length=1, max_length=120)
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_scope(self) -> _StructuredMechanicalClaim:
        self.normalized_key = " ".join(self.normalized_key.split())
        if not self.claim_payload:
            raise ValueError("claim_payload cannot be empty")
        if self.exact_applicability and self.vehicle_configuration_id is None:
            raise ValueError(
                "vehicle_configuration_id is required for exact applicability"
            )
        repair_claim = self.claim_domain in {
            "repair_requirement",
            "repair_procedure",
        }
        if repair_claim and not self.repair_key:
            raise ValueError("repair_key is required for repair claims")
        if not repair_claim and self.repair_key is not None:
            raise ValueError("repair_key is only valid for repair claims")
        return self


class _StructuredMechanicalClaimDocument(BaseModel):
    claims: list[_StructuredMechanicalClaim] = Field(min_length=1, max_length=1000)


class StructuredMechanicalClaimAdapter:
    """Deterministically normalize already-structured backend evidence.

    This adapter performs no network access and grants no source authority. It
    converts an approved provider/file payload into reviewer-visible candidate
    rows only. Source authority is applied later during curator publication.
    """

    adapter_key = "structured_mechanical_claims"
    adapter_version = "v1"
    required_capability = MECHANICAL_CLAIM_CAPABILITY
    supported_provider_kinds = frozenset(
        {"internal_data", "vehicle_data", "manufacturer"}
    )

    def extract(self, record: RawProviderRecord) -> tuple[ExtractedCandidate, ...]:
        try:
            document = _StructuredMechanicalClaimDocument.model_validate(
                record.raw_payload
            )
        except ValidationError as exc:
            raise ExtractionError(
                "raw provider record does not match the structured mechanical-claim contract"
            ) from exc

        candidates: list[ExtractedCandidate] = []
        for claim in document.claims:
            mechanical_claim = claim.model_dump(
                mode="json",
                exclude={"confidence"},
            )
            candidates.append(
                ExtractedCandidate(
                    candidate_type=MECHANICAL_CLAIM_CANDIDATE,
                    candidate_payload={"mechanical_claim": mechanical_claim},
                    vehicle_configuration_id=claim.vehicle_configuration_id,
                    confidence=claim.confidence,
                )
            )
        return tuple(candidates)


def _vehicle_snapshot(configuration: VehicleConfiguration) -> dict[str, object]:
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


def _validate_execution_boundary(
    *,
    provider: ProviderMetadata,
    source: SourceMetadata,
    adapter: ExtractionAdapter,
) -> None:
    if not provider.enabled:
        raise ExtractionError("provider is disabled")
    if provider.provider_kind not in adapter.supported_provider_kinds:
        raise ExtractionError("provider kind is not supported by this extraction adapter")
    if adapter.required_capability not in provider.capabilities:
        raise ExtractionError("provider does not declare the required extraction capability")
    if source.license_status != "approved":
        raise ExtractionError("source is not approved for automated extraction")
    if not source.automation_allowed:
        raise ExtractionError("source does not permit automated extraction")


async def extract_and_stage_provider_record(
    session: AsyncSession,
    *,
    provider: ProviderMetadata,
    source: SourceMetadata,
    adapter: ExtractionAdapter,
    record: RawProviderRecord,
) -> StagedExtractionResult:
    """Normalize one raw record into pending staging candidates atomically.

    The caller supplies a trusted provider→source mapping. This function does
    not fetch remote data, resolve secrets, review evidence, create claims, or
    write canonical truth.
    """

    _validate_execution_boundary(provider=provider, source=source, adapter=adapter)
    candidates = adapter.extract(record)
    if not candidates:
        raise ExtractionError("extraction adapter produced no candidate facts")

    vehicle_snapshots: dict[UUID, dict[str, object]] = {}
    for candidate in candidates:
        if candidate.confidence is not None and not 0 <= candidate.confidence <= 1:
            raise ExtractionError("candidate confidence must be between 0 and 1")
        configuration_id = candidate.vehicle_configuration_id
        if configuration_id is None or configuration_id in vehicle_snapshots:
            continue
        configuration = await session.get(VehicleConfiguration, configuration_id)
        if configuration is None:
            raise ExtractionError(
                "extracted candidate references an unknown vehicle configuration"
            )
        vehicle_snapshots[configuration_id] = _vehicle_snapshot(configuration)

    extraction_method = f"{adapter.adapter_key}@{adapter.adapter_version}"
    if len(extraction_method) > 64:
        raise ExtractionError("adapter identity exceeds staging extraction_method limit")
    collector_version = extraction_method

    batch = await create_ingestion_batch(
        session,
        source_name=source.source_key,
        source_type=source.source_class,
        collector_version=collector_version,
    )
    staged: list[CatalogSourceRecord] = []
    inserted_count = 0
    for candidate in candidates:
        provenance = {
            **record.provenance,
            "provider_connection_id": str(provider.id),
            "provider_key": provider.provider_key,
            "provider_kind": provider.provider_kind,
            "source_registry_id": str(source.id),
            "source_license_status_at_extraction": source.license_status,
            "adapter_key": adapter.adapter_key,
            "adapter_version": adapter.adapter_version,
        }
        staged_record, inserted = await stage_source_record(
            session,
            batch_id=batch.id,
            record=StageRecordInput(
                source_record_id=record.source_record_id,
                source_url=record.source_url,
                fetched_at=record.fetched_at,
                observed_at=record.observed_at,
                candidate_type=candidate.candidate_type,
                raw_payload=record.raw_payload,
                candidate_payload=candidate.candidate_payload,
                vehicle_identity=(
                    vehicle_snapshots.get(candidate.vehicle_configuration_id)
                    if candidate.vehicle_configuration_id is not None
                    else None
                ),
                provenance=provenance,
                extraction_method=extraction_method,
                confidence=candidate.confidence,
            ),
        )
        staged.append(staged_record)
        inserted_count += int(inserted)

    await complete_ingestion_batch(session, batch.id)
    return StagedExtractionResult(
        ingestion_batch_id=batch.id,
        staging_record_ids=tuple(item.id for item in staged),
        inserted_count=inserted_count,
    )
