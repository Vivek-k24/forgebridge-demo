"""Compatibility boundary between canonical knowledge and private repair state.

Canonical repair-definition, requirement, procedure, evidence, and capability
models now live in :mod:`partgraph.knowledge.models`. The two private owner
readiness tables remain here temporarily and move with repair experience in
restructure PR 3/5.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from ..knowledge.models import (
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


__all__ = [
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
    "UserGarageInventoryItem",
    "RepairRequirementState",
]
