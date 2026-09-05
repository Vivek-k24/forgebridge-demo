from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..identity.vehicle.models import VehicleConfiguration, VehicleSpecificationProfile
from ..identity.vehicle.reconciliation import reconcile_vehicle_specification_profile
from ..identity.vehicle.specification_taxonomy import core_verification_decision
from .coverage_models import CatalogCoverageItem
from .models import CatalogIngestionBatch, CatalogSourceRecord, CatalogVerifiedEvidence
from .workbench_models import CatalogCollectionJob, CatalogWorkbenchSource
from .workbench_source_pipeline import EXTRACTION_METHOD, SourceFetchResult

COLLECTOR_VERSION = "local-workbench-v2"
VERIFIER = "partgraph_local_workbench_field_reconciler_v2"


def _now() -> datetime:
    return datetime.now(UTC)


def _stable_id(label: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"partgraph:local-workbench:{label}")


def vehicle_identity(configuration: VehicleConfiguration) -> dict[str, object]:
    return {
        "vehicle_configuration_id": str(configuration.id),
        "year": configuration.year,
        "market": configuration.market,
        "make": configuration.make,
        "model": configuration.model,
        "trim": configuration.trim,
        "engine": configuration.engine,
        "transmission": configuration.transmission,
        "drivetrain": configuration.drivetrain,
    }


async def _ingestion_batch(
    session: AsyncSession,
    job: CatalogCollectionJob,
    provider: str,
    source_class: str,
) -> CatalogIngestionBatch:
    batch_id = _stable_id(f"ingestion:{job.id}:{provider}:{COLLECTOR_VERSION}")
    existing = await session.get(CatalogIngestionBatch, batch_id)
    if existing is not None:
        if job.status == "completed" and existing.status == "open":
            existing.status = "completed"
            existing.completed_at = _now()
        return existing
    completed = job.status == "completed"
    batch = CatalogIngestionBatch(
        id=batch_id,
        source_name=f"local_workbench_{provider}",
        source_type=source_class,
        collector_version=COLLECTOR_VERSION,
        status="completed" if completed else "open",
        completed_at=_now() if completed else None,
    )
    session.add(batch)
    await session.flush()
    return batch


async def stage_source_result(
    session: AsyncSession,
    job: CatalogCollectionJob,
    configuration: VehicleConfiguration,
    result: SourceFetchResult,
) -> CatalogSourceRecord | None:
    if result.fetch_status != "success" or result.raw_sha256 is None:
        return None
    batch = await _ingestion_batch(
        session,
        job,
        result.provider,
        result.source_class,
    )
    dedupe_key = sha256(
        (
            f"{result.provider}\0{configuration.id}\0{result.source_url}\0"
            f"{result.raw_sha256}\0{EXTRACTION_METHOD}"
        ).encode()
    ).hexdigest()
    existing = await session.scalar(
        select(CatalogSourceRecord).where(CatalogSourceRecord.dedupe_key == dedupe_key)
    )
    if existing is not None:
        return existing

    now = _now()
    has_observations = bool(result.field_observations)
    record = CatalogSourceRecord(
        batch_id=batch.id,
        source_record_id=(
            f"workbench:{result.provider}:{configuration.id}:"
            f"{result.raw_sha256[:12]}:{EXTRACTION_METHOD}"
        ),
        source_url=result.source_url,
        fetched_at=now,
        observed_at=None,
        candidate_type="vehicle_specification_candidate",
        raw_sha256=result.raw_sha256,
        raw_payload={
            "cache_path": result.cache_path,
            "response": result.raw_metadata,
        },
        candidate_payload={
            "fields": result.field_observations,
            "matched_fields": result.matched_fields,
        },
        vehicle_identity=vehicle_identity(configuration),
        provenance={
            "capture_kind": "local_operator_collection",
            "workbench_job_id": str(job.id),
            "provider": result.provider,
            "source_class": result.source_class,
            "verification_rule": "three_independent_sources_per_field_no_fixed_source_maximum",
            "extraction_method": EXTRACTION_METHOD,
        },
        extraction_method=EXTRACTION_METHOD,
        confidence=None,
        # Here verified means the deterministic extraction was accepted as an
        # observation. The field itself is still candidate until reconciliation.
        review_status="verified" if has_observations else "pending",
        reviewed_at=now if has_observations else None,
        reviewed_by=VERIFIER if has_observations else None,
        dedupe_key=dedupe_key,
    )
    session.add(record)
    await session.flush()
    return record


async def record_source_attempt(
    session: AsyncSession,
    job: CatalogCollectionJob,
    configuration: VehicleConfiguration,
    result: SourceFetchResult,
) -> CatalogWorkbenchSource:
    existing = await session.scalar(
        select(CatalogWorkbenchSource).where(
            CatalogWorkbenchSource.job_id == job.id,
            CatalogWorkbenchSource.vehicle_configuration_id == configuration.id,
            CatalogWorkbenchSource.provider == result.provider,
        )
    )
    if existing is not None:
        return existing

    matched_fields = dict(result.matched_fields)
    matched_fields["source_class"] = result.source_class
    staged = await stage_source_result(session, job, configuration, result)
    if staged is not None:
        matched_fields["staging_record_id"] = str(staged.id)

    source = CatalogWorkbenchSource(
        job_id=job.id,
        vehicle_configuration_id=configuration.id,
        provider=result.provider,
        source_url=result.source_url,
        fetch_status=result.fetch_status,
        http_status=result.http_status,
        matched_fields=matched_fields,
        raw_sha256=result.raw_sha256,
        cache_path=result.cache_path,
        error=result.error,
        fetched_at=_now() if result.fetch_status == "success" else None,
    )
    session.add(source)
    await session.flush()
    return source


async def _promote_reconciled_fields(
    session: AsyncSession,
    configuration: VehicleConfiguration,
    reconciliation: dict[str, object],
) -> None:
    field_results = reconciliation.get("fields")
    if not isinstance(field_results, list):
        return

    accepted_by_field: dict[str, tuple[str, set[str]]] = {}
    for item in field_results:
        if not isinstance(item, dict):
            continue
        status = item.get("status")
        if status not in {"verified", "manufacturer_reported"}:
            continue
        field = item.get("field")
        sources = item.get("sources")
        if isinstance(field, str) and isinstance(sources, list):
            accepted_by_field[field] = (str(status), {str(source) for source in sources})
    if not accepted_by_field:
        return

    rows = (
        await session.execute(
            select(CatalogSourceRecord, CatalogIngestionBatch)
            .join(CatalogIngestionBatch, CatalogSourceRecord.batch_id == CatalogIngestionBatch.id)
            .where(
                CatalogSourceRecord.candidate_type == "vehicle_specification_candidate",
                CatalogSourceRecord.review_status == "verified",
                CatalogSourceRecord.vehicle_identity["vehicle_configuration_id"].astext
                == str(configuration.id),
            )
        )
    ).all()
    for staging, batch in rows:
        fields = staging.candidate_payload.get("fields")
        if not isinstance(fields, dict):
            continue
        contributed = {
            field: payload
            for field, payload in fields.items()
            if field in accepted_by_field and batch.source_name in accepted_by_field[field][1]
        }
        if not contributed:
            continue
        existing = await session.scalar(
            select(CatalogVerifiedEvidence).where(
                CatalogVerifiedEvidence.staging_record_id == staging.id
            )
        )
        if existing is not None:
            continue
        session.add(
            CatalogVerifiedEvidence(
                staging_record_id=staging.id,
                candidate_type=staging.candidate_type,
                verified_payload={
                    "fields": contributed,
                    "field_status": {
                        field: accepted_by_field[field][0]
                        for field in contributed
                    },
                },
                vehicle_identity=staging.vehicle_identity,
                source_name=batch.source_name,
                source_type=batch.source_type,
                source_record_id=staging.source_record_id,
                source_url=staging.source_url,
                raw_sha256=staging.raw_sha256,
                fetched_at=staging.fetched_at,
                observed_at=staging.observed_at,
                provenance=staging.provenance,
                extraction_method=staging.extraction_method,
                promoted_by=VERIFIER,
            )
        )


async def _upsert_profile(
    session: AsyncSession,
    configuration: VehicleConfiguration,
    reconciliation: dict[str, object],
    core: dict[str, object],
) -> None:
    patch = reconciliation.get("promotable_profile_patch")
    if not isinstance(patch, dict) or not patch:
        return
    fields = reconciliation.get("fields")
    counts = (
        [
            int(item.get("match_count", 0))
            for item in fields
            if isinstance(item, dict)
            and item.get("status") in {"verified", "manufacturer_reported"}
        ]
        if isinstance(fields, list)
        else []
    )
    source_match_count = max(1, max(counts, default=1))
    matrix = dict(reconciliation)
    matrix["core_configuration"] = core

    profile = await session.scalar(
        select(VehicleSpecificationProfile).where(
            VehicleSpecificationProfile.vehicle_configuration_id == configuration.id
        )
    )
    status = "verified" if core.get("verified") is True else "candidate"
    if profile is None:
        session.add(
            VehicleSpecificationProfile(
                vehicle_configuration_id=configuration.id,
                profile_version=1,
                verification_status=status,
                source_match_count=source_match_count,
                profile=patch,
                source_matrix=matrix,
            )
        )
        return
    # A later incomplete pass cannot silently erase previously accepted truth.
    # New conflicts remain visible in coverage/source_matrix for review.
    if profile.verification_status == "verified" and status != "verified":
        return
    profile.profile_version += 1
    profile.verification_status = status
    profile.source_match_count = source_match_count
    profile.profile = patch
    profile.source_matrix = matrix


async def reconcile_configuration(
    session: AsyncSession,
    coverage: CatalogCoverageItem,
    configuration: VehicleConfiguration,
) -> dict[str, object]:
    reconciliation = await reconcile_vehicle_specification_profile(session, configuration.id)
    fields_raw = reconciliation.get("fields")
    fields = fields_raw if isinstance(fields_raw, list) else []
    core = core_verification_decision(configuration, fields)
    reconciliation["core_configuration"] = core

    coverage.source_observation_count = int(reconciliation.get("independent_sources", 0))
    coverage.source_match_count = int(core.get("source_match_floor", 0))
    coverage.source_matrix = {
        "rule": "three_independent_sources_per_field_no_fixed_source_maximum",
        "observed_sources": reconciliation.get("independent_sources", 0),
        "observation_records": reconciliation.get("observation_records", 0),
        "field_summary": reconciliation.get("summary", {}),
        "sections": reconciliation.get("sections", {}),
        "core_configuration": core,
        "fields": fields,
    }

    previously_verified = (
        coverage.verification_status == "verified"
        or configuration.verification_status == "verified"
    )
    if core.get("verified") is True:
        coverage.verification_status = "verified"
        coverage.verified_at = coverage.verified_at or _now()
        configuration.verification_status = "verified"
        configuration.identity_source = "multi_source"
    elif core.get("conflict") is True:
        # Conflicting new evidence must be visible even when canonical identity
        # was previously verified. Canonical truth itself is not silently erased.
        coverage.verification_status = "conflict"
        if not previously_verified:
            coverage.verified_at = None
            configuration.verification_status = "unverified"
    elif previously_verified:
        # Mere absence/incompleteness in a later pass is not contradictory
        # evidence and therefore cannot silently downgrade an accepted profile.
        coverage.verification_status = "verified"
    else:
        coverage.verification_status = "unverified"
        coverage.verified_at = None
        configuration.verification_status = "unverified"

    await _upsert_profile(session, configuration, reconciliation, core)
    await _promote_reconciled_fields(session, configuration, reconciliation)
    return reconciliation


async def complete_ingestion_batches(session: AsyncSession, job_id: UUID) -> None:
    batches = list(
        await session.scalars(
            select(CatalogIngestionBatch).where(
                CatalogIngestionBatch.collector_version == COLLECTOR_VERSION,
                CatalogIngestionBatch.id.in_(
                    select(CatalogSourceRecord.batch_id).where(
                        CatalogSourceRecord.provenance["workbench_job_id"].astext == str(job_id)
                    )
                ),
            )
        )
    )
    for batch in batches:
        if batch.status == "open":
            batch.status = "completed"
            batch.completed_at = _now()
