from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ProcedureActionMilestone(Base):
    """Canonical meaning attached to a verified procedure action."""

    __tablename__ = "procedure_action_milestones"
    __table_args__ = (
        CheckConstraint(
            "milestone_type IN ('physical_replacement')",
            name="ck_procedure_action_milestones_type",
        ),
    )

    action_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("procedure_actions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    milestone_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RepairDownstreamRequirement(Base):
    """Required work activated by a verified repair milestone."""

    __tablename__ = "repair_downstream_requirements"
    __table_args__ = (
        CheckConstraint(
            "trigger_type IN ('action_completed', 'procedure_complete')",
            name="ck_repair_downstream_requirements_trigger_type",
        ),
        CheckConstraint(
            "support_state IN ('supported', 'professional_required', 'unsupported')",
            name="ck_repair_downstream_requirements_support_state",
        ),
        CheckConstraint(
            "(trigger_type = 'action_completed' AND trigger_action_id IS NOT NULL) OR "
            "(trigger_type = 'procedure_complete' AND trigger_action_id IS NULL)",
            name="ck_repair_downstream_requirements_trigger_scope",
        ),
        CheckConstraint(
            "(support_state = 'supported' AND target_repair_definition_id IS NOT NULL) OR "
            "(support_state IN ('professional_required', 'unsupported') "
            "AND target_repair_definition_id IS NULL)",
            name="ck_repair_downstream_requirements_target_scope",
        ),
        CheckConstraint(
            "target_repair_definition_id IS NULL OR "
            "target_repair_definition_id <> source_repair_definition_id",
            name="ck_repair_downstream_requirements_not_self",
        ),
        CheckConstraint("position >= 0", name="ck_repair_downstream_requirements_position"),
        UniqueConstraint(
            "source_repair_definition_id",
            "requirement_key",
            name="uq_repair_downstream_requirements_definition_key",
        ),
        UniqueConstraint(
            "source_repair_definition_id",
            "position",
            name="uq_repair_downstream_requirements_definition_position",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_repair_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repair_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requirement_key: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    trigger_type: Mapped[str] = mapped_column(String(24), nullable=False)
    trigger_action_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("procedure_actions.id", ondelete="CASCADE"),
    )
    support_state: Mapped[str] = mapped_column(String(32), nullable=False)
    target_repair_definition_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repair_definitions.id", ondelete="RESTRICT"),
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RepairDownstreamRequirementEvidence(Base):
    __tablename__ = "repair_downstream_requirement_evidence"

    downstream_requirement_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repair_downstream_requirements.id", ondelete="CASCADE"),
        primary_key=True,
    )
    mechanical_claim_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("mechanical_claims.id", ondelete="RESTRICT"),
        primary_key=True,
    )
