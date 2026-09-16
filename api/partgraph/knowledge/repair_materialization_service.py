from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import ErrorCode, PartGraphError
from ..identity.vehicle.models import VehicleConfiguration
from .claim_locks import lock_mechanical_claims
from .models import (
    CatalogSource,
    MechanicalClaim,
    ProcedureAction,
    ProcedureActionDependency,
    ProcedureActionEvidence,
    ProcedureActionRequirementUse,
    RepairCapabilityPolicy,
    RepairDefinition,
    RepairOperation,
    RequirementDefinition,
    RequirementUse,
    RequirementUseEvidence,
)
from .provenance import CanonicalConflict, CanonicalRecordEvidence, CanonicalRecordVersion
from .repair_materialization_contract import (
    RepairDefinitionMaterializationCreate,
    RepairDefinitionMaterializationRead,
    RequirementMaterializationSpec,
    action_expected,
    assert_payload_coverage,
    invalid_materialization,
    request_sha256,
    requirement_expected,
)


def _validate_claim_scope(
    claims: list[MechanicalClaim],
    *,
    claim_domain: str,
    vehicle_configuration_id: UUID,
    repair_key: str,
) -> None:
    for claim in claims:
        if claim.promotion_state != "verified":
            raise invalid_materialization(
                "Repair materialization requires verified mechanical claims only."
            )
        if claim.claim_domain != claim_domain:
            raise invalid_materialization(
                "A supporting claim belongs to the wrong mechanical domain."
            )
        if not claim.explicit_claim or not claim.exact_applicability:
            raise invalid_materialization(
                "Repair materialization requires explicit exact-applicability claims."
            )
        if claim.vehicle_configuration_id != vehicle_configuration_id:
            raise invalid_materialization(
                "A supporting claim belongs to a different vehicle configuration."
            )
        if claim.repair_key != repair_key:
            raise invalid_materialization(
                "A supporting claim belongs to a different repair scope."
            )


async def _load_verified_claims(
    db: AsyncSession,
    request: RepairDefinitionMaterializationCreate,
) -> dict[UUID, MechanicalClaim]:
    claim_ids = {
        claim_id
        for requirement in request.requirements
        for claim_id in requirement.supporting_claim_ids
    } | {
        claim_id
        for action in request.actions
        for claim_id in action.supporting_claim_ids
    }
    if not claim_ids:
        raise invalid_materialization(
            "Repair materialization requires at least one verified claim."
        )

    # Publication is a claim-state reader, not a claim-state writer. Shared
    # advisory locks serialize it with curator claim transitions without
    # granting the materializer UPDATE privilege on mechanical_claims.
    await lock_mechanical_claims(db, claim_ids, shared=True)
    claims = list(
        await db.scalars(
            select(MechanicalClaim).where(MechanicalClaim.id.in_(claim_ids))
        )
    )
    claim_by_id = {claim.id: claim for claim in claims}
    missing = sorted(claim_ids - set(claim_by_id), key=str)
    if missing:
        raise invalid_materialization(
            "One or more supporting mechanical claims do not exist.",
            details={"missing_claim_ids": [str(item) for item in missing]},
        )

    source_ids = {claim.source_id for claim in claims}
    sources = list(
        await db.scalars(select(CatalogSource).where(CatalogSource.id.in_(source_ids)))
    )
    if len(sources) != len(source_ids):
        raise invalid_materialization(
            "A supporting claim references an unavailable source registry entry."
        )
    unapproved = sorted(
        source.source_key for source in sources if source.license_status != "approved"
    )
    if unapproved:
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_SOURCE_NOT_APPROVED,
            message="Every supporting claim source must still be approved at publication time.",
            status_code=status.HTTP_409_CONFLICT,
            details={"source_keys": unapproved},
        )

    conflict_keys = {claim.conflict_key for claim in claims if claim.conflict_key is not None}
    if conflict_keys:
        blocked = list(
            await db.scalars(
                select(CanonicalConflict.conflict_key).where(
                    CanonicalConflict.conflict_key.in_(conflict_keys),
                    CanonicalConflict.conflict_state.in_(("open", "blocked")),
                )
            )
        )
        if blocked:
            raise invalid_materialization(
                "Supporting claims still have unresolved canonical conflicts.",
                details={"conflict_keys": sorted(blocked)},
            )

    for requirement in request.requirements:
        selected = [claim_by_id[item] for item in requirement.supporting_claim_ids]
        _validate_claim_scope(
            selected,
            claim_domain="repair_requirement",
            vehicle_configuration_id=request.vehicle_configuration_id,
            repair_key=request.repair_key,
        )
        assert_payload_coverage(
            selected,
            requirement_expected(requirement),
            fact_label=f"requirement[{requirement.use_key}]",
        )
    for action in request.actions:
        selected = [claim_by_id[item] for item in action.supporting_claim_ids]
        _validate_claim_scope(
            selected,
            claim_domain="repair_procedure",
            vehicle_configuration_id=request.vehicle_configuration_id,
            repair_key=request.repair_key,
        )
        assert_payload_coverage(
            selected,
            action_expected(action),
            fact_label=f"action[{action.action_key}]",
        )
    return claim_by_id


async def _existing_publication_read(
    db: AsyncSession,
    record_version: CanonicalRecordVersion,
) -> RepairDefinitionMaterializationRead:
    if record_version.canonical_domain != "repair" or record_version.record_type != "repair_definition":
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_PUBLICATION_IDEMPOTENCY_CONFLICT,
            message="Idempotency key is already bound to a different canonical publication.",
            status_code=status.HTTP_409_CONFLICT,
        )
    definition = await db.get(RepairDefinition, record_version.record_id)
    if definition is None:
        raise invalid_materialization(
            "Canonical publication references a missing repair definition."
        )
    claim_ids = list(
        await db.scalars(
            select(CanonicalRecordEvidence.mechanical_claim_id).where(
                CanonicalRecordEvidence.record_version_id == record_version.id,
                CanonicalRecordEvidence.mechanical_claim_id.is_not(None),
            )
        )
    )
    superseded_definition_id: UUID | None = None
    if record_version.supersedes_version_id is not None:
        previous = await db.get(CanonicalRecordVersion, record_version.supersedes_version_id)
        if previous is None or previous.record_type != "repair_definition":
            raise invalid_materialization(
                "Canonical repair supersession chain is incomplete."
            )
        superseded_definition_id = previous.record_id
    return RepairDefinitionMaterializationRead(
        repair_definition_id=definition.id,
        vehicle_configuration_id=definition.vehicle_configuration_id,
        repair_key=definition.repair_key,
        version=definition.version,
        definition_status=definition.status,
        canonical_record_version_id=record_version.id,
        superseded_definition_id=superseded_definition_id,
        supporting_claim_ids=sorted(
            {item for item in claim_ids if item is not None}, key=str
        ),
        idempotent=True,
    )


async def _canonical_requirement_definitions(
    db: AsyncSession,
    requirements: list[RequirementMaterializationSpec],
) -> dict[str, RequirementDefinition]:
    first_by_key: dict[str, RequirementMaterializationSpec] = {}
    for spec in requirements:
        first_by_key.setdefault(spec.requirement_key, spec)

    result: dict[str, RequirementDefinition] = {}
    for requirement_key in sorted(first_by_key):
        spec = first_by_key[requirement_key]
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"requirement-definition:{requirement_key}"},
        )
        definition = await db.scalar(
            select(RequirementDefinition).where(
                RequirementDefinition.requirement_key == requirement_key
            )
        )
        if definition is None:
            definition = RequirementDefinition(
                id=uuid4(),
                requirement_key=requirement_key,
                category=spec.category,
                display_name=spec.display_name,
                default_unit=spec.default_unit,
            )
            db.add(definition)
            await db.flush()
        elif (
            definition.category != spec.category
            or definition.display_name != spec.display_name
            or definition.default_unit != spec.default_unit
        ):
            raise invalid_materialization(
                "Existing canonical requirement metadata conflicts with verified claims.",
                details={"requirement_key": requirement_key},
            )
        result[requirement_key] = definition
    return result


async def materialize_repair_definition_service(
    db: AsyncSession,
    *,
    request: RepairDefinitionMaterializationCreate,
    actor: str,
    idempotency_key: str,
) -> RepairDefinitionMaterializationRead:
    request_digest = request_sha256(request)
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"repair-publication:{idempotency_key}"},
    )
    existing = await db.scalar(
        select(CanonicalRecordVersion).where(
            CanonicalRecordVersion.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        if existing.request_sha256 != request_digest:
            raise PartGraphError(
                code=ErrorCode.KNOWLEDGE_PUBLICATION_IDEMPOTENCY_CONFLICT,
                message="Idempotency key was already used with a different publication request.",
                status_code=status.HTTP_409_CONFLICT,
            )
        return await _existing_publication_read(db, existing)

    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"repair-scope:{request.vehicle_configuration_id}:{request.repair_key}"},
    )
    if await db.get(VehicleConfiguration, request.vehicle_configuration_id) is None:
        raise invalid_materialization(
            "Repair materialization references an unknown vehicle configuration."
        )

    capability_policy = await db.scalar(
        select(RepairCapabilityPolicy).where(
            RepairCapabilityPolicy.policy_key == request.capability_policy_key
        )
    )
    if capability_policy is None:
        raise invalid_materialization(
            "Repair materialization references an unknown capability policy."
        )
    if capability_policy.guidance_state != "supported" and request.actions:
        raise invalid_materialization(
            "Professional-required or prohibited repairs cannot publish guided procedure actions."
        )

    claim_by_id = await _load_verified_claims(db, request)
    current_definitions = list(
        await db.scalars(
            select(RepairDefinition)
            .where(
                RepairDefinition.vehicle_configuration_id == request.vehicle_configuration_id,
                RepairDefinition.repair_key == request.repair_key,
                RepairDefinition.status == "verified",
            )
            .with_for_update()
        )
    )
    if len(current_definitions) > 1:
        raise invalid_materialization(
            "Repair scope contains multiple current verified definitions."
        )
    current = current_definitions[0] if current_definitions else None
    if current is None and request.expected_current_definition_id is not None:
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_PUBLICATION_CONFLICT,
            message="Expected current repair definition no longer exists.",
            status_code=status.HTTP_409_CONFLICT,
        )
    if current is not None and request.expected_current_definition_id != current.id:
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_PUBLICATION_CONFLICT,
            message="Repair definition changed since the curator loaded it.",
            status_code=status.HTTP_409_CONFLICT,
            details={"current_repair_definition_id": str(current.id)},
        )

    previous_version: CanonicalRecordVersion | None = None
    next_version = 1
    now = datetime.now(UTC)
    if current is not None:
        previous_version = await db.scalar(
            select(CanonicalRecordVersion)
            .where(
                CanonicalRecordVersion.canonical_domain == "repair",
                CanonicalRecordVersion.record_type == "repair_definition",
                CanonicalRecordVersion.record_id == current.id,
                CanonicalRecordVersion.version == current.version,
            )
            .with_for_update()
        )
        if previous_version is None or previous_version.publication_state != "verified":
            raise invalid_materialization(
                "Current repair definition is missing its verified publication envelope."
            )
        next_version = current.version + 1
        current.status = "superseded"
        previous_version.publication_state = "superseded"
        await db.flush()

    definition = RepairDefinition(
        id=uuid4(),
        vehicle_configuration_id=request.vehicle_configuration_id,
        capability_policy_id=capability_policy.id,
        repair_key=request.repair_key,
        title=request.title,
        version=next_version,
        status="verified",
        verified_at=now,
    )
    db.add(definition)
    await db.flush()
    if current is not None:
        current.superseded_by_id = definition.id
        await db.flush()

    operations_by_key: dict[str, RepairOperation] = {}
    for spec in sorted(request.operations, key=lambda item: (item.position, item.operation_key)):
        operation = RepairOperation(
            id=uuid4(),
            repair_definition_id=definition.id,
            operation_key=spec.operation_key,
            label=spec.label,
            position=spec.position,
        )
        db.add(operation)
        operations_by_key[spec.operation_key] = operation
    await db.flush()

    requirement_definitions = await _canonical_requirement_definitions(
        db, request.requirements
    )
    use_by_key: dict[str, RequirementUse] = {}
    for spec in request.requirements:
        use = RequirementUse(
            id=uuid4(),
            repair_definition_id=definition.id,
            operation_id=(
                operations_by_key[spec.operation_key].id
                if spec.operation_key is not None
                else None
            ),
            requirement_definition_id=requirement_definitions[spec.requirement_key].id,
            quantity=spec.quantity,
            unit=spec.unit,
            necessity=spec.necessity,
            fulfillment_mode=spec.fulfillment_mode,
            timing=spec.timing,
        )
        db.add(use)
        use_by_key[spec.use_key] = use
    await db.flush()
    for spec in request.requirements:
        for claim_id in spec.supporting_claim_ids:
            db.add(
                RequirementUseEvidence(
                    requirement_use_id=use_by_key[spec.use_key].id,
                    mechanical_claim_id=claim_id,
                )
            )

    action_by_key: dict[str, ProcedureAction] = {}
    for spec in sorted(request.actions, key=lambda item: (item.position, item.action_key)):
        action = ProcedureAction(
            id=uuid4(),
            repair_definition_id=definition.id,
            action_key=spec.action_key,
            title=spec.title,
            instruction=spec.instruction,
            warning_text=spec.warning_text,
            workspace_note=spec.workspace_note,
            position=spec.position,
            skippable=spec.skippable,
        )
        db.add(action)
        action_by_key[spec.action_key] = action
    await db.flush()
    for spec in request.actions:
        action = action_by_key[spec.action_key]
        for prerequisite_key in spec.prerequisite_action_keys:
            db.add(
                ProcedureActionDependency(
                    action_id=action.id,
                    prerequisite_action_id=action_by_key[prerequisite_key].id,
                )
            )
        for use_key in spec.requirement_use_keys:
            db.add(
                ProcedureActionRequirementUse(
                    action_id=action.id,
                    requirement_use_id=use_by_key[use_key].id,
                )
            )
        for claim_id in spec.supporting_claim_ids:
            db.add(
                ProcedureActionEvidence(
                    action_id=action.id,
                    mechanical_claim_id=claim_id,
                )
            )

    record_version = CanonicalRecordVersion(
        id=uuid4(),
        canonical_domain="repair",
        record_type="repair_definition",
        record_id=definition.id,
        version=definition.version,
        publication_state="verified",
        supersedes_version_id=previous_version.id if previous_version is not None else None,
        idempotency_key=idempotency_key,
        request_sha256=request_digest,
        published_by=actor,
        published_at=now,
    )
    db.add(record_version)
    await db.flush()

    supporting_claim_ids = sorted(claim_by_id, key=str)
    for claim_id in supporting_claim_ids:
        claim = claim_by_id[claim_id]
        db.add(
            CanonicalRecordEvidence(
                record_version_id=record_version.id,
                verified_evidence_id=claim.verified_evidence_id,
                mechanical_claim_id=claim.id,
                evidence_role="supports",
            )
        )
    await db.flush()

    return RepairDefinitionMaterializationRead(
        repair_definition_id=definition.id,
        vehicle_configuration_id=definition.vehicle_configuration_id,
        repair_key=definition.repair_key,
        version=definition.version,
        definition_status=definition.status,
        canonical_record_version_id=record_version.id,
        superseded_definition_id=current.id if current is not None else None,
        supporting_claim_ids=supporting_claim_ids,
    )
