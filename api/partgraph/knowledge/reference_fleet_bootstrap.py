from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select, text

from ..database import session_factory
from ..identity.vehicle.models import VehicleConfiguration
from ..identity.vehicle.schemas import VehicleConfigurationInput
from ..identity.vehicle.service import resolve_configuration
from .canonical_claim_materialization import materialize_verified_mechanical_claim_service
from .completion_models import RepairDownstreamRequirement
from .downstream_materialization import (
    DownstreamRequirementMaterializationCreate,
    materialize_downstream_requirement_service,
)
from .models import (
    CatalogSource,
    CatalogVerifiedEvidence,
    MechanicalClaim,
    ProcedureAction,
    ProcedureActionEvidence,
    RepairDefinition,
)
from .repair_materialization_contract import RepairDefinitionMaterializationCreate
from .repair_materialization_service import materialize_repair_definition_service

REFERENCE_ROOT = Path(__file__).resolve().parents[2] / "data" / "reference"
FLEET_INDEX_PATH = REFERENCE_ROOT / "phase8_reference_fleet_v1.json"
PRIMARY_REPAIR_MANIFEST = (
    REFERENCE_ROOT / "2009_honda_civic_hybrid_repairs_v1" / "manifest.json"
)
BOOTSTRAP_NAMESPACE = uuid5(NAMESPACE_URL, "https://partgraph.local/reference-fleet-bootstrap/v1")
BOOTSTRAP_LOCK_KEY = "partgraph-preview-reference-fleet-v2"
PREVIEW_BRANCH = "partgraph-mvp-consolidation"

_REQUIREMENT_FIELDS = {
    "use_key",
    "requirement_key",
    "category",
    "display_name",
    "default_unit",
    "quantity",
    "unit",
    "necessity",
    "fulfillment_mode",
    "timing",
    "operation_key",
}
_ACTION_FIELDS = {
    "action_key",
    "title",
    "instruction",
    "warning_text",
    "workspace_note",
    "position",
    "skippable",
    "prerequisite_action_keys",
    "requirement_use_keys",
}


@dataclass(frozen=True, slots=True)
class ReferenceDataset:
    root: Path
    manifest: dict[str, Any]
    repairs: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class ReferenceFleetPublication:
    vehicle_configurations: int
    repair_definitions: int
    downstream_requirements: int
    already_complete: bool


def preview_reference_bootstrap_enabled() -> bool:
    return (
        os.getenv("VERCEL_ENV") == "preview"
        and os.getenv("VERCEL_GIT_COMMIT_REF") == PREVIEW_BRANCH
    )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_dataset(manifest_path: Path) -> ReferenceDataset:
    manifest = _load_json(manifest_path)
    if manifest.get("schema_version") != 1:
        raise ValueError(f"Unsupported reference manifest: {manifest_path}")
    source_keys = {str(item["source_key"]) for item in manifest["sources"]}
    repairs: list[dict[str, Any]] = []
    for repair_entry in manifest["repairs"]:
        if str(repair_entry["source_key"]) not in source_keys:
            raise ValueError(
                f"Repair source is not registered in {manifest_path}: "
                f"{repair_entry['source_key']}"
            )
        repair = _load_json(manifest_path.parent / str(repair_entry["path"]))
        if repair["dataset_key"] != manifest["dataset_key"]:
            raise ValueError(f"Repair dataset mismatch: {repair_entry['path']}")
        if repair["repair_key"] != repair_entry["repair_key"]:
            raise ValueError(f"Repair key mismatch: {repair_entry['path']}")
        if len(repair["requirements"]) != int(repair_entry["requirement_count"]):
            raise ValueError(f"Requirement count mismatch: {repair_entry['path']}")
        if len(repair["actions"]) != int(repair_entry["action_count"]):
            raise ValueError(f"Action count mismatch: {repair_entry['path']}")
        repairs.append(repair)
    return ReferenceDataset(
        root=manifest_path.parent,
        manifest=manifest,
        repairs=tuple(repairs),
    )


def load_reference_fleet() -> tuple[ReferenceDataset, ...]:
    index = _load_json(FLEET_INDEX_PATH)
    if index.get("schema_version") != 2:
        raise ValueError("Reference fleet index must use schema version 2.")

    datasets = [_load_dataset(PRIMARY_REPAIR_MANIFEST)]
    seen = {str(datasets[0].manifest["dataset_key"])}
    for item in index["datasets"]:
        dataset = _load_dataset(REFERENCE_ROOT / str(item["path"]) / str(item["manifest"]))
        expected = tuple(str(path) for path in item["repairs"])
        actual = tuple(str(entry["path"]) for entry in dataset.manifest["repairs"])
        if actual != expected:
            raise ValueError(
                f"Fleet index and manifest repair order differ for {item['path']}."
            )
        key = str(dataset.manifest["dataset_key"])
        if key in seen:
            raise ValueError(f"Duplicate reference dataset: {key}")
        seen.add(key)
        datasets.append(dataset)
    return tuple(datasets)


def _stable_uuid(kind: str, token: str) -> UUID:
    return uuid5(BOOTSTRAP_NAMESPACE, f"{kind}:{token}")


def _digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _claim_payload(item: dict[str, Any], *, requirement: bool) -> dict[str, Any]:
    excluded = {"source_pages", "use_key"} if requirement else {"source_pages"}
    return {key: value for key, value in item.items() if key not in excluded}


async def _resolve_configurations(
    datasets: tuple[ReferenceDataset, ...],
) -> dict[str, UUID]:
    resolved: dict[str, UUID] = {}
    async with session_factory() as db:
        for dataset in datasets:
            configuration, _ = await resolve_configuration(
                db,
                VehicleConfigurationInput.model_validate(dataset.manifest["vehicle"]),
            )
            resolved[str(dataset.manifest["dataset_key"])] = configuration.id
    return resolved


async def _ensure_source(
    db,
    source_definition: dict[str, Any],
) -> CatalogSource:
    source_key = str(source_definition["source_key"])
    source = await db.scalar(
        select(CatalogSource).where(CatalogSource.source_key == source_key)
    )
    if source is not None:
        if (
            source.source_class != source_definition["source_class"]
            or source.license_status != "approved"
            or source.automation_allowed
        ):
            raise ValueError(
                f"Reference source governance conflicts with stored source {source_key}."
            )
        return source

    if source_definition["license_status"] != "approved":
        raise ValueError(f"Reference source is not approved: {source_key}")
    if source_definition.get("automation_allowed", False):
        raise ValueError(
            f"Reference bootstrap must not enable source automation: {source_key}"
        )

    source = CatalogSource(
        id=_stable_uuid("source", source_key),
        source_key=source_key,
        display_name=str(source_definition["document"]),
        source_class=str(source_definition["source_class"]),
        license_status="approved",
        automation_allowed=False,
        terms_url=source_definition.get("terms_url"),
        notes="Curated source used by the non-production PartGraph reference fleet.",
    )
    db.add(source)
    await db.flush()
    return source


async def _ensure_claim(
    db,
    *,
    dataset_key: str,
    source: CatalogSource,
    source_url: str,
    vehicle_configuration_id: UUID,
    claim_domain: str,
    item_key: str,
    payload: dict[str, Any],
    repair_key: str | None,
    source_pages: list[int] | None,
) -> MechanicalClaim:
    token = f"{dataset_key}:{repair_key or 'vehicle'}:{claim_domain}:{item_key}"
    claim_id = _stable_uuid("claim", token)
    existing = await db.get(MechanicalClaim, claim_id)
    if existing is not None:
        if (
            existing.source_id != source.id
            or existing.vehicle_configuration_id != vehicle_configuration_id
            or existing.claim_domain != claim_domain
            or existing.repair_key != repair_key
            or existing.claim_payload != payload
            or existing.promotion_state != "verified"
        ):
            raise ValueError(f"Stored reference claim conflicts with {token}.")
        return existing

    evidence_id = _stable_uuid("evidence", token)
    evidence = await db.get(CatalogVerifiedEvidence, evidence_id)
    if evidence is None:
        evidence = CatalogVerifiedEvidence(
            id=evidence_id,
            staging_record_id=_stable_uuid("staging", token),
            candidate_type="mechanical_claim_candidate",
            verified_payload={"mechanical_claim": payload},
            vehicle_identity={"vehicle_configuration_id": str(vehicle_configuration_id)},
            source_name=source.source_key,
            source_type=source.source_class,
            source_record_id=f"reference:{_digest({'token': token})[:32]}",
            source_url=source_url,
            raw_sha256=_digest(payload),
            fetched_at=datetime.now(UTC),
            provenance={
                "fixture": "preview-reference-fleet-bootstrap",
                "dataset_key": dataset_key,
                "source_pages": source_pages or [],
            },
            extraction_method="curated_reference_fixture",
            promoted_by="partgraph-reference-review",
        )
        db.add(evidence)
        await db.flush()

    claim = MechanicalClaim(
        id=claim_id,
        source_id=source.id,
        verified_evidence_id=evidence.id,
        vehicle_configuration_id=vehicle_configuration_id,
        claim_domain=claim_domain,
        claim_risk="normal",
        normalized_key=f"reference.{claim_domain}.{_digest({'token': token})[:24]}",
        repair_key=repair_key,
        claim_payload=payload,
        explicit_claim=True,
        exact_applicability=True,
        promotion_state="verified",
        reviewed_at=datetime.now(UTC),
        reviewed_by="partgraph-reference-review",
    )
    db.add(claim)
    await db.flush()
    return claim


async def _materialize_identity(
    db,
    *,
    dataset: ReferenceDataset,
    configuration: VehicleConfiguration,
    sources: dict[str, CatalogSource],
) -> None:
    if configuration.verification_status == "verified":
        return
    if configuration.verification_status != "unverified":
        raise ValueError(
            f"Unsupported reference identity state: {configuration.verification_status}"
        )

    source_definition = dataset.manifest["sources"][0]
    source = sources[str(source_definition["source_key"])]
    payload = dict(dataset.manifest["vehicle"])
    claim = await _ensure_claim(
        db,
        dataset_key=str(dataset.manifest["dataset_key"]),
        source=source,
        source_url=str(source_definition["url"]),
        vehicle_configuration_id=configuration.id,
        claim_domain="vehicle_identity",
        item_key="vehicle-identity",
        payload=payload,
        repair_key=None,
        source_pages=None,
    )

    await db.execute(text("SET LOCAL ROLE partgraph_materializer"))
    try:
        await materialize_verified_mechanical_claim_service(
            db,
            claim_id=claim.id,
            actor="preview-reference-bootstrap",
            idempotency_key=f"ref.identity.{str(configuration.id)[:8]}.{_digest(payload)[:12]}",
        )
    finally:
        await db.execute(text("RESET ROLE"))
    await db.refresh(configuration)


async def _publish_repair(
    db,
    *,
    dataset: ReferenceDataset,
    repair: dict[str, Any],
    vehicle_configuration_id: UUID,
    sources: dict[str, CatalogSource],
) -> tuple[RepairDefinition, dict[str, UUID]]:
    repair_key = str(repair["repair_key"])
    current = await db.scalar(
        select(RepairDefinition).where(
            RepairDefinition.vehicle_configuration_id == vehicle_configuration_id,
            RepairDefinition.repair_key == repair_key,
            RepairDefinition.status == "verified",
        )
    )
    if current is not None:
        action_claims: dict[str, UUID] = {}
        actions = list(
            await db.scalars(
                select(ProcedureAction).where(
                    ProcedureAction.repair_definition_id == current.id
                )
            )
        )
        for action in actions:
            claim_id = await db.scalar(
                select(ProcedureActionEvidence.mechanical_claim_id).where(
                    ProcedureActionEvidence.action_id == action.id
                )
            )
            if claim_id is not None:
                action_claims[action.action_key] = claim_id
        return current, action_claims

    manifest_entry = next(
        item for item in dataset.manifest["repairs"] if item["repair_key"] == repair_key
    )
    source_definition = next(
        item
        for item in dataset.manifest["sources"]
        if item["source_key"] == manifest_entry["source_key"]
    )
    source = sources[str(source_definition["source_key"])]

    requirement_claim_ids: dict[str, UUID] = {}
    for item in repair["requirements"]:
        payload = _claim_payload(item, requirement=True)
        claim = await _ensure_claim(
            db,
            dataset_key=str(dataset.manifest["dataset_key"]),
            source=source,
            source_url=str(source_definition["url"]),
            vehicle_configuration_id=vehicle_configuration_id,
            claim_domain="repair_requirement",
            item_key=str(item["use_key"]),
            payload=payload,
            repair_key=repair_key,
            source_pages=item.get("source_pages") or repair.get("source_pages"),
        )
        requirement_claim_ids[str(item["use_key"])] = claim.id

    action_claim_ids: dict[str, UUID] = {}
    for item in repair["actions"]:
        payload = _claim_payload(item, requirement=False)
        claim = await _ensure_claim(
            db,
            dataset_key=str(dataset.manifest["dataset_key"]),
            source=source,
            source_url=str(source_definition["url"]),
            vehicle_configuration_id=vehicle_configuration_id,
            claim_domain="repair_procedure",
            item_key=str(item["action_key"]),
            payload=payload,
            repair_key=repair_key,
            source_pages=item.get("source_pages") or repair.get("source_pages"),
        )
        action_claim_ids[str(item["action_key"])] = claim.id

    requirements = []
    for item in repair["requirements"]:
        spec = {key: item[key] for key in _REQUIREMENT_FIELDS if key in item}
        spec["supporting_claim_ids"] = [requirement_claim_ids[str(item["use_key"])]]
        requirements.append(spec)

    actions = []
    for item in repair["actions"]:
        spec = {key: item[key] for key in _ACTION_FIELDS if key in item}
        spec["supporting_claim_ids"] = [action_claim_ids[str(item["action_key"])]]
        actions.append(spec)

    request = RepairDefinitionMaterializationCreate(
        vehicle_configuration_id=vehicle_configuration_id,
        repair_key=repair_key,
        title=str(repair["title"]),
        capability_policy_key=str(repair["capability_policy_key"]),
        operations=repair["operations"],
        requirements=requirements,
        actions=actions,
    )
    request_hash = _digest(request.model_dump(mode="json"))
    await db.execute(text("SET LOCAL ROLE partgraph_materializer"))
    try:
        publication = await materialize_repair_definition_service(
            db,
            request=request,
            actor="preview-reference-bootstrap",
            idempotency_key=(
                f"ref.repair.{_digest({'dataset': dataset.manifest['dataset_key'], 'repair': repair_key})[:16]}."
                f"{request_hash[:12]}"
            ),
        )
    finally:
        await db.execute(text("RESET ROLE"))

    definition = await db.get(RepairDefinition, publication.repair_definition_id)
    if definition is None:
        raise ValueError(f"Materialized repair disappeared: {repair_key}")
    return definition, action_claim_ids


async def _publish_downstream(
    db,
    *,
    datasets: tuple[ReferenceDataset, ...],
    definition_by_scope: dict[tuple[str, str], RepairDefinition],
    action_claims_by_scope: dict[tuple[str, str], dict[str, UUID]],
) -> int:
    published = 0
    for dataset in datasets:
        dataset_key = str(dataset.manifest["dataset_key"])
        for repair in dataset.repairs:
            source_key = str(repair["repair_key"])
            source_definition = definition_by_scope[(dataset_key, source_key)]
            for position, action in enumerate(repair["actions"]):
                requirement_key = action.get("downstream_requirement_key")
                if not requirement_key:
                    continue

                target_definition = None
                target_repair_key = action.get("downstream_target_repair_key")
                if action["downstream_support_state"] == "supported":
                    if not target_repair_key:
                        raise ValueError(
                            f"Supported downstream action has no target: {source_key}"
                        )
                    target_definition = definition_by_scope[
                        (dataset_key, str(target_repair_key))
                    ]

                claim_id = action_claims_by_scope.get((dataset_key, source_key), {}).get(
                    str(action["action_key"])
                )
                if claim_id is None:
                    stored_action = await db.scalar(
                        select(ProcedureAction).where(
                            ProcedureAction.repair_definition_id == source_definition.id,
                            ProcedureAction.action_key == action["action_key"],
                        )
                    )
                    if stored_action is None:
                        raise ValueError(
                            f"Downstream trigger action is missing: {action['action_key']}"
                        )
                    claim_id = await db.scalar(
                        select(ProcedureActionEvidence.mechanical_claim_id).where(
                            ProcedureActionEvidence.action_id == stored_action.id
                        )
                    )
                if claim_id is None:
                    raise ValueError(
                        f"Downstream trigger action has no supporting claim: {action['action_key']}"
                    )

                request = DownstreamRequirementMaterializationCreate(
                    source_repair_definition_id=source_definition.id,
                    requirement_key=str(requirement_key),
                    title=str(action["downstream_title"]),
                    detail=action.get("downstream_detail"),
                    trigger_type=str(action["downstream_trigger_type"]),
                    trigger_action_key=action.get("downstream_trigger_action_key"),
                    support_state=str(action["downstream_support_state"]),
                    target_repair_definition_id=(
                        None if target_definition is None else target_definition.id
                    ),
                    milestone_type=action.get("milestone_type"),
                    position=0,
                    supporting_claim_ids=[claim_id],
                )
                await db.execute(text("SET LOCAL ROLE partgraph_materializer"))
                try:
                    result = await materialize_downstream_requirement_service(
                        db,
                        request=request,
                    )
                finally:
                    await db.execute(text("RESET ROLE"))
                if not result.idempotent:
                    published += 1
    return published


async def publish_reference_fleet() -> ReferenceFleetPublication:
    datasets = load_reference_fleet()
    configuration_ids = await _resolve_configurations(datasets)

    async with session_factory() as db:
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": BOOTSTRAP_LOCK_KEY},
        )

        sources: dict[str, CatalogSource] = {}
        for dataset in datasets:
            for source_definition in dataset.manifest["sources"]:
                source = await _ensure_source(db, source_definition)
                sources[source.source_key] = source

        for dataset in datasets:
            dataset_key = str(dataset.manifest["dataset_key"])
            configuration = await db.get(
                VehicleConfiguration,
                configuration_ids[dataset_key],
            )
            if configuration is None:
                raise ValueError(f"Reference configuration disappeared: {dataset_key}")
            await _materialize_identity(
                db,
                dataset=dataset,
                configuration=configuration,
                sources=sources,
            )

        definition_by_scope: dict[tuple[str, str], RepairDefinition] = {}
        action_claims_by_scope: dict[tuple[str, str], dict[str, UUID]] = {}
        for dataset in datasets:
            dataset_key = str(dataset.manifest["dataset_key"])
            configuration_id = configuration_ids[dataset_key]
            for repair in dataset.repairs:
                definition, action_claims = await _publish_repair(
                    db,
                    dataset=dataset,
                    repair=repair,
                    vehicle_configuration_id=configuration_id,
                    sources=sources,
                )
                scope = (dataset_key, str(repair["repair_key"]))
                definition_by_scope[scope] = definition
                action_claims_by_scope[scope] = action_claims

        downstream_published = await _publish_downstream(
            db,
            datasets=datasets,
            definition_by_scope=definition_by_scope,
            action_claims_by_scope=action_claims_by_scope,
        )
        await db.commit()

        repair_count = sum(len(dataset.repairs) for dataset in datasets)
        downstream_count = int(
            await db.scalar(select(text("count(*)")).select_from(RepairDownstreamRequirement))
            or 0
        )
        return ReferenceFleetPublication(
            vehicle_configurations=len(configuration_ids),
            repair_definitions=repair_count,
            downstream_requirements=downstream_count,
            already_complete=downstream_published == 0,
        )
