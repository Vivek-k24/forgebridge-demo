from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class CapabilityBoundaryDefinition(Base):
    """Canonical non-completable safety/capability boundary definition.

    A supported repair has no active boundary at the relevant scope. These
    definitions represent the explicit states where PartGraph must not treat
    the affected repair or action as user-completable.
    """

    __tablename__ = "capability_boundary_definitions"
    __table_args__ = (
        CheckConstraint(
            "boundary_kind IN ('computer_service_tool', 'high_voltage_internal', "
            "'specialized_procedure', 'professional_only', 'other')",
            name="ck_capability_boundary_definitions_kind",
        ),
        CheckConstraint(
            "guidance_state IN ('information_only', 'professional_required', "
            "'prohibited', 'unsupported_indefinitely')",
            name="ck_capability_boundary_definitions_state",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    boundary_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    boundary_kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    guidance_state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    rationale: Mapped[str] = mapped_column(String(500), nullable=False)
    user_message: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class RepairCapabilityBoundary(Base):
    """Repair-level boundary for a versioned exact repair definition."""

    __tablename__ = "repair_capability_boundaries"
    __table_args__ = (
        UniqueConstraint(
            "repair_definition_id",
            "boundary_definition_id",
            name="uq_repair_capability_boundaries_definition",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    repair_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repair_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    boundary_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("capability_boundary_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ProcedureActionCapabilityBoundary(Base):
    """Action-level boundary marking an explicit non-completable stop point."""

    __tablename__ = "procedure_action_capability_boundaries"
    __table_args__ = (
        UniqueConstraint(
            "action_id",
            name="uq_procedure_action_capability_boundaries_action",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    action_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("procedure_actions.id", ondelete="CASCADE"),
        nullable=False,
    )
    boundary_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("capability_boundary_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
