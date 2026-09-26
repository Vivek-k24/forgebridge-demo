from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class RepairDownstreamRequirementState(Base):
    """Owner-private activation and resolution state for downstream work."""

    __tablename__ = "repair_downstream_requirement_states"
    __table_args__ = (
        CheckConstraint(
            "state IN ('pending', 'satisfied')",
            name="ck_repair_downstream_requirement_states_state",
        ),
        CheckConstraint(
            "resolution_kind IS NULL OR resolution_kind IN "
            "('linked_session_complete', 'external_service_confirmed')",
            name="ck_repair_downstream_requirement_states_resolution_kind",
        ),
        CheckConstraint(
            "(state = 'pending' AND resolution_kind IS NULL AND satisfied_at IS NULL) OR "
            "(state = 'satisfied' AND resolution_kind IS NOT NULL AND satisfied_at IS NOT NULL)",
            name="ck_repair_downstream_requirement_states_resolution",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repair_sessions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    downstream_requirement_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repair_downstream_requirements.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    resolution_kind: Mapped[str | None] = mapped_column(String(32))
    resolution_session_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repair_sessions.id", ondelete="RESTRICT"),
    )
    resolution_note: Mapped[str | None] = mapped_column(String(500))
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    satisfied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
