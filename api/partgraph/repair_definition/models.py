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
)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


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
    """Requirement scope only; Block 11 owns user-facing procedural instructions."""

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


class UserGarageInventoryItem(Base):
    __tablename__ = "user_garage_inventory_items"
    __table_args__ = (
        CheckConstraint(
            "quantity_available >= 0",
            name="ck_user_garage_inventory_quantity",
        ),
        UniqueConstraint(
            "user_id",
            "requirement_definition_id",
            name="uq_user_garage_inventory_requirement",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("requirement_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity_available: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, default=Decimal("0")
    )
    unit: Mapped[str | None] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class RepairRequirementState(Base):
    __tablename__ = "repair_requirement_states"
    __table_args__ = (
        CheckConstraint(
            "readiness_state IN ('have', 'missing', 'ordered', 'unavailable')",
            name="ck_repair_requirement_states_state",
        ),
        CheckConstraint(
            "quantity_available >= 0",
            name="ck_repair_requirement_states_quantity",
        ),
        UniqueConstraint(
            "user_id",
            "session_id",
            "requirement_definition_id",
            name="uq_repair_requirement_states_session_requirement_definition",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repair_sessions.id", ondelete="CASCADE"), nullable=False
    )
    requirement_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("requirement_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity_available: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, default=Decimal("0")
    )
    readiness_state: Mapped[str] = mapped_column(String(16), nullable=False)
    procurement_reference: Mapped[str | None] = mapped_column(String(240))
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
