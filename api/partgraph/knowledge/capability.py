from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
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


class ProcedureActionCapabilityBoundary(Base):
    """Canonical action-level capability boundary within a verified procedure.

    RepairCapabilityPolicy remains the repair-level gate. This table represents
    the point inside an otherwise supported procedure where PartGraph must stop
    or become information-only because the remaining operation exceeds the
    product's supported capability.
    """

    __tablename__ = "procedure_action_capability_boundaries"
    __table_args__ = (
        CheckConstraint(
            "boundary_kind IN ('computer_service_tool', 'high_voltage_internal', "
            "'specialized_procedure', 'professional_only', 'other')",
            name="ck_procedure_action_capability_boundaries_kind",
        ),
        CheckConstraint(
            "completion_allowed = false",
            name="ck_procedure_action_capability_boundaries_not_completable",
        ),
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
    capability_policy_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repair_capability_policies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    boundary_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    boundary_code: Mapped[str] = mapped_column(String(80), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    completion_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
