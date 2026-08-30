from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base

STAGING_SCHEMA = "catalog_staging"


class CatalogIngestionBatch(Base):
    __tablename__ = "ingestion_batches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'completed', 'failed')",
            name="ck_catalog_ingestion_batches_status",
        ),
        {"schema": STAGING_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    collector_version: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="open", server_default=text("'open'")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CatalogSourceRecord(Base):
    __tablename__ = "source_records"
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_catalog_source_records_confidence",
        ),
        CheckConstraint(
            "review_status IN ('pending', 'verified', 'rejected')",
            name="ck_catalog_source_records_review_status",
        ),
        {"schema": STAGING_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{STAGING_SCHEMA}.ingestion_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_record_id: Mapped[str] = mapped_column(String(256), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    candidate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    candidate_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    vehicle_identity: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    provenance: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    review_status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default=text("'pending'")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CatalogVerifiedEvidence(Base):
    """Immutable verified evidence snapshot, not canonical truth by itself."""

    __tablename__ = "catalog_verified_evidence"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    staging_record_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, unique=True)
    candidate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    verified_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    vehicle_identity: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(256), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    raw_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provenance: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(64), nullable=False)
    promoted_by: Mapped[str] = mapped_column(String(128), nullable=False)
    promoted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CatalogSource(Base):
    """Governance metadata for a source; ingestion still lands in staging."""

    __tablename__ = "catalog_sources"
    __table_args__ = (
        CheckConstraint(
            "source_class IN ('government', 'oem_service', 'licensed_oem_derived', "
            "'oem_parts', 'industry_standard', 'retailer', 'community')",
            name="ck_catalog_sources_class",
        ),
        CheckConstraint(
            "license_status IN ('unreviewed', 'approved', 'prohibited')",
            name="ck_catalog_sources_license_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_key: Mapped[str] = mapped_column(String(96), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_class: Mapped[str] = mapped_column(String(32), nullable=False)
    license_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unreviewed"
    )
    automation_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    terms_url: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MechanicalClaim(Base):
    """Normalized claim supported by immutable verified evidence.

    A claim becomes canonical repair truth only when attached to the exact
    repair-definition structure that consumes it.
    """

    __tablename__ = "mechanical_claims"
    __table_args__ = (
        CheckConstraint(
            "claim_domain IN ('vehicle_identity', 'safety_campaign', "
            "'repair_requirement', 'repair_procedure', 'part_fitment')",
            name="ck_mechanical_claims_domain",
        ),
        CheckConstraint(
            "claim_risk IN ('normal', 'safety_critical')",
            name="ck_mechanical_claims_risk",
        ),
        CheckConstraint(
            "promotion_state IN ('staged', 'needs_review', 'verified', 'rejected', "
            "'conflict', 'superseded')",
            name="ck_mechanical_claims_promotion_state",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("catalog_sources.id", ondelete="RESTRICT"), nullable=False
    )
    verified_evidence_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(CatalogVerifiedEvidence.id, ondelete="RESTRICT"),
        nullable=False,
    )
    vehicle_configuration_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_configurations.id", ondelete="RESTRICT"),
    )
    claim_domain: Mapped[str] = mapped_column(String(32), nullable=False)
    claim_risk: Mapped[str] = mapped_column(String(24), nullable=False, default="normal")
    normalized_key: Mapped[str] = mapped_column(String(160), nullable=False)
    repair_key: Mapped[str | None] = mapped_column(String(120))
    claim_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    explicit_claim: Mapped[bool] = mapped_column(Boolean, nullable=False)
    exact_applicability: Mapped[bool] = mapped_column(Boolean, nullable=False)
    promotion_state: Mapped[str] = mapped_column(String(24), nullable=False)
    conflict_key: Mapped[str | None] = mapped_column(String(128), index=True)
    superseded_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("mechanical_claims.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(128))


class RepairCapabilityPolicy(Base):
    __tablename__ = "repair_capability_policies"
    __table_args__ = (
        CheckConstraint(
            "guidance_state IN ('supported', 'professional_required', 'prohibited')",
            name="ck_repair_capability_policies_guidance_state",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    policy_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    guidance_state: Mapped[str] = mapped_column(String(32), nullable=False)
    rationale: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RepairDefinition(Base):
    __tablename__ = "repair_definitions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'verified', 'superseded')",
            name="ck_repair_definitions_status",
        ),
        UniqueConstraint(
            "vehicle_configuration_id",
            "repair_key",
            "version",
            name="uq_repair_definitions_vehicle_key_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    vehicle_configuration_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_configurations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    capability_policy_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repair_capability_policies.id", ondelete="RESTRICT"),
        index=True,
    )
    repair_key: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repair_definitions.id", ondelete="SET NULL")
    )


class RepairOperation(Base):
    """Requirement scope within one exact repair definition."""

    __tablename__ = "repair_operations"
    __table_args__ = (
        UniqueConstraint(
            "repair_definition_id",
            "operation_key",
            name="uq_repair_operations_definition_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    repair_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repair_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation_key: Mapped[str] = mapped_column(String(120), nullable=False)
    label: Mapped[str] = mapped_column(String(180), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RequirementDefinition(Base):
    __tablename__ = "requirement_definitions"
    __table_args__ = (
        CheckConstraint(
            "category IN ('tool', 'equipment', 'part', 'fluid', 'consumable', "
            "'hardware', 'workspace', 'safety_prerequisite')",
            name="ck_requirement_definitions_category",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    requirement_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    default_unit: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RequirementUse(Base):
    __tablename__ = "requirement_uses"
    __table_args__ = (
        CheckConstraint(
            "necessity IN ('required', 'recommended')",
            name="ck_requirement_uses_necessity",
        ),
        CheckConstraint(
            "fulfillment_mode IN ('reusable', 'consumed', 'reuse_existing', "
            "'replacement_required', 'replace_if_damaged')",
            name="ck_requirement_uses_fulfillment_mode",
        ),
        CheckConstraint(
            "timing IN ('before_start', 'whole_repair', 'operation')",
            name="ck_requirement_uses_timing",
        ),
        CheckConstraint(
            "quantity IS NULL OR quantity > 0",
            name="ck_requirement_uses_quantity",
        ),
        CheckConstraint(
            "(timing = 'operation' AND operation_id IS NOT NULL) OR "
            "(timing <> 'operation')",
            name="ck_requirement_uses_operation_scope",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    repair_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repair_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repair_operations.id", ondelete="CASCADE")
    )
    requirement_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("requirement_definitions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    unit: Mapped[str | None] = mapped_column(String(32))
    necessity: Mapped[str] = mapped_column(String(16), nullable=False, default="required")
    fulfillment_mode: Mapped[str] = mapped_column(String(24), nullable=False)
    timing: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RequirementUseEvidence(Base):
    __tablename__ = "requirement_use_evidence"

    requirement_use_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("requirement_uses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    mechanical_claim_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("mechanical_claims.id", ondelete="RESTRICT"),
        primary_key=True,
    )


class ProcedureAction(Base):
    __tablename__ = "procedure_actions"
    __table_args__ = (
        CheckConstraint("position >= 0", name="ck_procedure_actions_position"),
        UniqueConstraint(
            "repair_definition_id",
            "action_key",
            name="uq_procedure_actions_definition_key",
        ),
        UniqueConstraint(
            "repair_definition_id",
            "position",
            name="uq_procedure_actions_definition_position",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    repair_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repair_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_key: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    warning_text: Mapped[str | None] = mapped_column(Text)
    workspace_note: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    skippable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProcedureActionDependency(Base):
    __tablename__ = "procedure_action_dependencies"
    __table_args__ = (
        CheckConstraint(
            "action_id <> prerequisite_action_id",
            name="ck_procedure_action_dependencies_not_self",
        ),
    )

    action_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("procedure_actions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    prerequisite_action_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("procedure_actions.id", ondelete="CASCADE"),
        primary_key=True,
    )


class ProcedureActionRequirementUse(Base):
    __tablename__ = "procedure_action_requirement_uses"

    action_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("procedure_actions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    requirement_use_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("requirement_uses.id", ondelete="RESTRICT"),
        primary_key=True,
    )


class ProcedureActionEvidence(Base):
    __tablename__ = "procedure_action_evidence"

    action_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("procedure_actions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    mechanical_claim_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("mechanical_claims.id", ondelete="RESTRICT"),
        primary_key=True,
    )


__all__ = [
    "STAGING_SCHEMA",
    "CatalogIngestionBatch",
    "CatalogSourceRecord",
    "CatalogVerifiedEvidence",
    "CatalogSource",
    "MechanicalClaim",
    "RepairCapabilityPolicy",
    "RepairDefinition",
    "RepairOperation",
    "RequirementDefinition",
    "RequirementUse",
    "RequirementUseEvidence",
    "ProcedureAction",
    "ProcedureActionDependency",
    "ProcedureActionRequirementUse",
    "ProcedureActionEvidence",
]
