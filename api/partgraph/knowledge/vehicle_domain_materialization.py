from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import ErrorCode, ErrorEnvelope, PartGraphError
from ..identity.auth.dependencies import AuthSessionDep, require_csrf
from ..identity.auth.roles import CuratorUserDep, assume_materializer_database_role
from ..identity.vehicle.models import VehicleConfiguration
from .canonical_claim_materialization import _assert_claim_publishable
from .claim_locks import lock_mechanical_claims
from .models import MechanicalClaim
from .provenance import CanonicalRecordEvidence, CanonicalRecordVersion
from .repair_materialization_contract import IDEMPOTENCY_PATTERN, invalid_materialization
from .specifications import SpecificationDefinition, VehicleSpecificationValue
from .vehicle_structure import VehicleStructureNode

_SUPPORTED_CLAIM_DOMAINS = frozenset({"vehicle_structure", "vehicle_specification"})
_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

StructureNodeType = Literal["system", "subsystem", "assembly", "subassembly"]
SpecificationType = Literal[
    "torque",
    "pressure",
    "flow",
    "clearance",
    "dimension",
    "capacity",
    "service_limit",
    "electrical",
    "temperature",
    "speed",
    "time",
    "mass",
    "volume",
    "ratio",
    "other",
]
SpecificationValueKind = Literal["scalar", "range", "maximum", "minimum", "text"]


def _key(value: str, field: str, maximum: int) -> str:
    cleaned = value.strip().lower()
    if not cleaned or len(cleaned) > maximum or _KEY_PATTERN.fullmatch(cleaned) is None:
        raise ValueError(f"{field} must be a normalized lowercase key")
    return cleaned


def _text(value: str, field: str, maximum: int) -> str:
    cleaned = " ".join(value.split())
    if not cleaned or len(cleaned) > maximum:
        raise ValueError(f"{field} must contain 1-{maximum} characters")
    return cleaned


def _optional_text(value: str | None, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    if not cleaned:
        return None
    if len(cleaned) > maximum:
        raise ValueError(f"{field} must contain at most {maximum} characters")
    return cleaned


class VehicleStructureClaim(BaseModel):
    node_key: str = Field(min_length=1, max_length=160)
    node_type: StructureNodeType
    display_name: str = Field(min_length=1, max_length=180)
    parent_node_key: str | None = Field(default=None, max_length=160)
    placement: str | None = Field(default=None, max_length=96)
    position: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def normalize(self) -> VehicleStructureClaim:
        self.node_key = _key(self.node_key, "node_key", 160)
        self.display_name = _text(self.display_name, "display_name", 180)
        if self.parent_node_key is not None:
            self.parent_node_key = _key(self.parent_node_key, "parent_node_key", 160)
            if self.parent_node_key == self.node_key:
                raise ValueError("a structure node cannot be its own parent")
        self.placement = _optional_text(self.placement, "placement", 96)
        return self


class VehicleSpecificationClaim(BaseModel):
    specification_key: str = Field(min_length=1, max_length=180)
    specification_type: SpecificationType
    value_kind: SpecificationValueKind
    display_name: str = Field(min_length=1, max_length=180)
    quantity_kind: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=1000)
    application_key: str = Field(min_length=1, max_length=180)
    nominal_value: Decimal | None = None
    minimum_value: Decimal | None = None
    maximum_value: Decimal | None = None
    unit: str | None = Field(default=None, max_length=48)
    text_value: str | None = Field(default=None, max_length=255)
    qualifier_key: str = Field(default="", max_length=128)
    conditions: dict[str, object] = Field(default_factory=dict)

    @field_validator("nominal_value", "minimum_value", "maximum_value")
    @classmethod
    def finite_decimal(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and not value.is_finite():
            raise ValueError("specification numeric values must be finite")
        return value

    @model_validator(mode="after")
    def normalize_and_validate(self) -> VehicleSpecificationClaim:
        self.specification_key = _key(self.specification_key, "specification_key", 180)
        self.display_name = _text(self.display_name, "display_name", 180)
        self.application_key = _key(self.application_key, "application_key", 180)
        self.qualifier_key = (
            _key(self.qualifier_key, "qualifier_key", 128) if self.qualifier_key else ""
        )
        self.quantity_kind = _optional_text(self.quantity_kind, "quantity_kind", 64)
        self.description = _optional_text(self.description, "description", 1000)
        self.unit = _optional_text(self.unit, "unit", 48)
        self.text_value = _optional_text(self.text_value, "text_value", 255)

        if (
            self.minimum_value is not None
            and self.maximum_value is not None
            and self.minimum_value > self.maximum_value
        ):
            raise ValueError("minimum_value cannot exceed maximum_value")
        if self.value_kind == "scalar" and self.nominal_value is None:
            raise ValueError("scalar specifications require nominal_value")
        if self.value_kind == "range" and (
            self.minimum_value is None or self.maximum_value is None
        ):
            raise ValueError("range specifications require minimum_value and maximum_value")
        if self.value_kind == "maximum" and self.maximum_value is None:
            raise ValueError("maximum specifications require maximum_value")
        if self.value_kind == "minimum" and self.minimum_value is None:
            raise ValueError("minimum specifications require minimum_value")
        if self.value_kind == "text" and self.text_value is None:
            raise ValueError("text specifications require text_value")
        if all(
            value is None
            for value in (
                self.nominal_value,
                self.minimum_value,
                self.maximum_value,
                self.text_value,
            )
        ):
            raise ValueError("a specification claim must contain a value")
        return self


class VehicleDomainMaterializationRead(BaseModel):
    mechanical_claim_id: UUID
    claim_domain: Literal["vehicle_structure", "vehicle_specification"]
    canonical_domain: Literal["structure", "specification"]
    record_type: Literal["vehicle_structure_node", "vehicle_specification_value"]
    record_id: UUID
    vehicle_configuration_id: UUID
    canonical_record_version_id: UUID
    version: int
    idempotent: bool = False


router = APIRouter(
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
IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$",
    ),
]


def _target(claim: MechanicalClaim) -> tuple[str, str]:
    if claim.claim_domain == "vehicle_structure":
        return "structure", "vehicle_structure_node"
    if claim.claim_domain == "vehicle_specification":
        return "specification", "vehicle_specification_value"
    raise invalid_materialization("Mechanical claim is not a vehicle-domain materialization claim.")


def _request_sha256(claim: MechanicalClaim) -> str:
    payload = json.dumps(
        {"mechanical_claim_id": str(claim.id), "claim_domain": claim.claim_domain},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


async def _existing_idempotent(
    db: AsyncSession,
    *,
    claim: MechanicalClaim,
    idempotency_key: str,
    request_digest: str,
) -> VehicleDomainMaterializationRead | None:
    existing = await db.scalar(
        select(CanonicalRecordVersion).where(
            CanonicalRecordVersion.idempotency_key == idempotency_key
        )
    )
    if existing is None:
        return None
    if existing.request_sha256 != request_digest:
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_PUBLICATION_IDEMPOTENCY_CONFLICT,
            message="Idempotency key was already used with a different publication request.",
            status_code=status.HTTP_409_CONFLICT,
        )
    canonical_domain, record_type = _target(claim)
    if existing.canonical_domain != canonical_domain or existing.record_type != record_type:
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_PUBLICATION_IDEMPOTENCY_CONFLICT,
            message="Idempotency key is bound to a different canonical publication target.",
            status_code=status.HTTP_409_CONFLICT,
        )
    evidence = await db.scalar(
        select(CanonicalRecordEvidence).where(
            CanonicalRecordEvidence.record_version_id == existing.id,
            CanonicalRecordEvidence.mechanical_claim_id == claim.id,
        )
    )
    if evidence is None:
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_PUBLICATION_IDEMPOTENCY_CONFLICT,
            message="Idempotency publication does not contain the requested supporting claim.",
            status_code=status.HTTP_409_CONFLICT,
        )
    assert claim.vehicle_configuration_id is not None
    return VehicleDomainMaterializationRead(
        mechanical_claim_id=claim.id,
        claim_domain=claim.claim_domain,  # type: ignore[arg-type]
        canonical_domain=canonical_domain,  # type: ignore[arg-type]
        record_type=record_type,  # type: ignore[arg-type]
        record_id=existing.record_id,
        vehicle_configuration_id=claim.vehicle_configuration_id,
        canonical_record_version_id=existing.id,
        version=existing.version,
        idempotent=True,
    )


async def _existing_claim_publication(
    db: AsyncSession,
    *,
    claim: MechanicalClaim,
    canonical_domain: str,
    record_type: str,
) -> VehicleDomainMaterializationRead | None:
    version = await db.scalar(
        select(CanonicalRecordVersion)
        .join(
            CanonicalRecordEvidence,
            CanonicalRecordEvidence.record_version_id == CanonicalRecordVersion.id,
        )
        .where(
            CanonicalRecordEvidence.mechanical_claim_id == claim.id,
            CanonicalRecordVersion.canonical_domain == canonical_domain,
            CanonicalRecordVersion.record_type == record_type,
            CanonicalRecordVersion.publication_state == "verified",
        )
        .order_by(CanonicalRecordVersion.version.desc())
    )
    if version is None:
        return None
    assert claim.vehicle_configuration_id is not None
    return VehicleDomainMaterializationRead(
        mechanical_claim_id=claim.id,
        claim_domain=claim.claim_domain,  # type: ignore[arg-type]
        canonical_domain=canonical_domain,  # type: ignore[arg-type]
        record_type=record_type,  # type: ignore[arg-type]
        record_id=version.record_id,
        vehicle_configuration_id=claim.vehicle_configuration_id,
        canonical_record_version_id=version.id,
        version=version.version,
        idempotent=True,
    )


async def _publish_version(
    db: AsyncSession,
    *,
    claim: MechanicalClaim,
    canonical_domain: str,
    record_type: str,
    record_id: UUID,
    actor: str,
    idempotency_key: str,
    request_digest: str,
) -> VehicleDomainMaterializationRead:
    maximum_version = await db.scalar(
        select(func.max(CanonicalRecordVersion.version)).where(
            CanonicalRecordVersion.canonical_domain == canonical_domain,
            CanonicalRecordVersion.record_type == record_type,
            CanonicalRecordVersion.record_id == record_id,
        )
    )
    current = await db.scalar(
        select(CanonicalRecordVersion)
        .where(
            CanonicalRecordVersion.canonical_domain == canonical_domain,
            CanonicalRecordVersion.record_type == record_type,
            CanonicalRecordVersion.record_id == record_id,
            CanonicalRecordVersion.publication_state == "verified",
        )
        .with_for_update()
    )
    if current is not None:
        current.publication_state = "superseded"
        await db.flush()

    version = CanonicalRecordVersion(
        id=uuid4(),
        canonical_domain=canonical_domain,
        record_type=record_type,
        record_id=record_id,
        version=int(maximum_version or 0) + 1,
        publication_state="verified",
        supersedes_version_id=current.id if current is not None else None,
        idempotency_key=idempotency_key,
        request_sha256=request_digest,
        published_by=actor,
        published_at=datetime.now(UTC),
    )
    db.add(version)
    await db.flush()
    db.add(
        CanonicalRecordEvidence(
            record_version_id=version.id,
            verified_evidence_id=claim.verified_evidence_id,
            mechanical_claim_id=claim.id,
            evidence_role="supports",
        )
    )
    await db.flush()

    assert claim.vehicle_configuration_id is not None
    return VehicleDomainMaterializationRead(
        mechanical_claim_id=claim.id,
        claim_domain=claim.claim_domain,  # type: ignore[arg-type]
        canonical_domain=canonical_domain,  # type: ignore[arg-type]
        record_type=record_type,  # type: ignore[arg-type]
        record_id=record_id,
        vehicle_configuration_id=claim.vehicle_configuration_id,
        canonical_record_version_id=version.id,
        version=version.version,
    )


async def _materialize_structure(
    db: AsyncSession,
    *,
    claim: MechanicalClaim,
    actor: str,
    idempotency_key: str,
    request_digest: str,
) -> VehicleDomainMaterializationRead:
    assert claim.vehicle_configuration_id is not None
    try:
        payload = VehicleStructureClaim.model_validate(claim.claim_payload)
    except ValueError as exc:
        raise invalid_materialization("Vehicle-structure claim payload is invalid.") from exc

    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"canonical-structure:{claim.vehicle_configuration_id}:{payload.node_key}"},
    )
    parent: VehicleStructureNode | None = None
    if payload.parent_node_key is not None:
        parent = await db.scalar(
            select(VehicleStructureNode).where(
                VehicleStructureNode.vehicle_configuration_id == claim.vehicle_configuration_id,
                VehicleStructureNode.node_key == payload.parent_node_key,
            )
        )
        if parent is None:
            raise invalid_materialization(
                "Vehicle-structure claim references a parent node that is not canonical yet."
            )

    existing_publication = await _existing_claim_publication(
        db,
        claim=claim,
        canonical_domain="structure",
        record_type="vehicle_structure_node",
    )
    if existing_publication is not None:
        return existing_publication

    row = await db.scalar(
        select(VehicleStructureNode).where(
            VehicleStructureNode.vehicle_configuration_id == claim.vehicle_configuration_id,
            VehicleStructureNode.node_key == payload.node_key,
        )
    )
    parent_id = parent.id if parent is not None else None
    if row is None:
        row = VehicleStructureNode(
            id=uuid4(),
            vehicle_configuration_id=claim.vehicle_configuration_id,
            node_key=payload.node_key,
            node_type=payload.node_type,
            display_name=payload.display_name,
            parent_node_id=parent_id,
            placement=payload.placement,
            position=payload.position,
        )
        db.add(row)
        await db.flush()
    elif (
        row.node_type != payload.node_type
        or row.display_name != payload.display_name
        or row.parent_node_id != parent_id
        or row.placement != payload.placement
        or row.position != payload.position
    ):
        raise invalid_materialization(
            "Verified structure claim conflicts with an existing canonical structure row; "
            "canonical structure is not overwritten automatically."
        )

    return await _publish_version(
        db,
        claim=claim,
        canonical_domain="structure",
        record_type="vehicle_structure_node",
        record_id=row.id,
        actor=actor,
        idempotency_key=idempotency_key,
        request_digest=request_digest,
    )


def _definition_matches(row: SpecificationDefinition, payload: VehicleSpecificationClaim) -> bool:
    return (
        row.specification_type == payload.specification_type
        and row.value_kind == payload.value_kind
        and row.display_name == payload.display_name
        and row.quantity_kind == payload.quantity_kind
        and row.description == payload.description
    )


def _value_matches(row: VehicleSpecificationValue, payload: VehicleSpecificationClaim) -> bool:
    return (
        row.nominal_value == payload.nominal_value
        and row.minimum_value == payload.minimum_value
        and row.maximum_value == payload.maximum_value
        and row.unit == payload.unit
        and row.text_value == payload.text_value
        and row.conditions == payload.conditions
        and row.physical_entity_id is None
        and row.material_definition_id is None
    )


async def _materialize_specification(
    db: AsyncSession,
    *,
    claim: MechanicalClaim,
    actor: str,
    idempotency_key: str,
    request_digest: str,
) -> VehicleDomainMaterializationRead:
    assert claim.vehicle_configuration_id is not None
    try:
        payload = VehicleSpecificationClaim.model_validate(claim.claim_payload)
    except ValueError as exc:
        raise invalid_materialization("Vehicle-specification claim payload is invalid.") from exc

    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"canonical-specification-definition:{payload.specification_key}"},
    )
    definition = await db.scalar(
        select(SpecificationDefinition).where(
            SpecificationDefinition.specification_key == payload.specification_key
        )
    )
    if definition is None:
        definition = SpecificationDefinition(
            id=uuid4(),
            specification_key=payload.specification_key,
            specification_type=payload.specification_type,
            value_kind=payload.value_kind,
            display_name=payload.display_name,
            quantity_kind=payload.quantity_kind,
            description=payload.description,
        )
        db.add(definition)
        await db.flush()
    elif not _definition_matches(definition, payload):
        raise invalid_materialization(
            "Verified specification claim conflicts with an existing specification definition; "
            "canonical specification identity is not overwritten automatically."
        )

    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {
            "key": (
                f"canonical-specification:{claim.vehicle_configuration_id}:{definition.id}:"
                f"{payload.application_key}:{payload.qualifier_key}"
            )
        },
    )
    existing_publication = await _existing_claim_publication(
        db,
        claim=claim,
        canonical_domain="specification",
        record_type="vehicle_specification_value",
    )
    if existing_publication is not None:
        return existing_publication

    row = await db.scalar(
        select(VehicleSpecificationValue).where(
            VehicleSpecificationValue.vehicle_configuration_id == claim.vehicle_configuration_id,
            VehicleSpecificationValue.specification_definition_id == definition.id,
            VehicleSpecificationValue.application_key == payload.application_key,
            VehicleSpecificationValue.qualifier_key == payload.qualifier_key,
        )
    )
    if row is None:
        row = VehicleSpecificationValue(
            id=uuid4(),
            vehicle_configuration_id=claim.vehicle_configuration_id,
            specification_definition_id=definition.id,
            application_key=payload.application_key,
            nominal_value=payload.nominal_value,
            minimum_value=payload.minimum_value,
            maximum_value=payload.maximum_value,
            unit=payload.unit,
            text_value=payload.text_value,
            qualifier_key=payload.qualifier_key,
            conditions=payload.conditions,
        )
        db.add(row)
        await db.flush()
    elif not _value_matches(row, payload):
        raise invalid_materialization(
            "Verified specification claim conflicts with an existing canonical specification value; "
            "canonical specifications are not overwritten automatically."
        )

    return await _publish_version(
        db,
        claim=claim,
        canonical_domain="specification",
        record_type="vehicle_specification_value",
        record_id=row.id,
        actor=actor,
        idempotency_key=idempotency_key,
        request_digest=request_digest,
    )


async def materialize_vehicle_domain_claim_service(
    db: AsyncSession,
    *,
    claim_id: UUID,
    actor: str,
    idempotency_key: str,
) -> VehicleDomainMaterializationRead:
    await lock_mechanical_claims(db, [claim_id], shared=True)
    claim = await db.get(MechanicalClaim, claim_id)
    if claim is None:
        raise PartGraphError(
            code=ErrorCode.KNOWLEDGE_MATERIALIZATION_INVALID,
            message="Mechanical claim not found for canonical materialization.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if claim.claim_domain not in _SUPPORTED_CLAIM_DOMAINS:
        raise invalid_materialization("Mechanical claim is not supported by this materializer.")

    await _assert_claim_publishable(db, claim)
    assert claim.vehicle_configuration_id is not None
    if await db.get(VehicleConfiguration, claim.vehicle_configuration_id) is None:
        raise invalid_materialization("Mechanical claim references an unknown vehicle configuration.")

    request_digest = _request_sha256(claim)
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"canonical-publication:{idempotency_key}"},
    )
    existing = await _existing_idempotent(
        db,
        claim=claim,
        idempotency_key=idempotency_key,
        request_digest=request_digest,
    )
    if existing is not None:
        return existing

    if claim.claim_domain == "vehicle_structure":
        return await _materialize_structure(
            db,
            claim=claim,
            actor=actor,
            idempotency_key=idempotency_key,
            request_digest=request_digest,
        )
    return await _materialize_specification(
        db,
        claim=claim,
        actor=actor,
        idempotency_key=idempotency_key,
        request_digest=request_digest,
    )


@router.post(
    "/mechanical-claims/{claim_id}/materialize-vehicle-domain",
    response_model=VehicleDomainMaterializationRead,
    dependencies=[CsrfDep],
)
async def materialize_vehicle_domain_claim(
    claim_id: UUID,
    user: CuratorUserDep,
    db: AuthSessionDep,
    idempotency_key: IdempotencyKey,
) -> VehicleDomainMaterializationRead:
    await assume_materializer_database_role(db)
    if IDEMPOTENCY_PATTERN.fullmatch(idempotency_key) is None:
        raise invalid_materialization("Idempotency-Key is invalid.")
    return await materialize_vehicle_domain_claim_service(
        db,
        claim_id=claim_id,
        actor=f"{user.id}:{user.role}",
        idempotency_key=idempotency_key,
    )
