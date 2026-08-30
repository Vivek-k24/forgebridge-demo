from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class RepairSession(Base):
    __tablename__ = "repair_sessions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_vehicle_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user_vehicles.id", ondelete="CASCADE"), nullable=False
    )
    repair_definition_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repair_definitions.id", ondelete="RESTRICT"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    creation_idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class RepairSessionEvent(Base):
    __tablename__ = "repair_session_events"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repair_sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_device_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RepairSessionProjection(Base):
    __tablename__ = "repair_session_projections"

    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repair_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    current_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repair_session_events.id", ondelete="RESTRICT"),
        nullable=False,
    )
    last_event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    editor_device_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    editor_lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    projection_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class RepairProcedureActionState(Base):
    __tablename__ = "repair_procedure_action_states"
    __table_args__ = (
        CheckConstraint(
            "progress_state IN ('completed', 'skipped', 'blocked')",
            name="ck_repair_procedure_action_states_progress",
        ),
        UniqueConstraint(
            "user_id",
            "session_id",
            "action_id",
            name="uq_repair_procedure_action_states_owner_session_action",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repair_sessions.id", ondelete="CASCADE"), nullable=False
    )
    action_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("procedure_actions.id", ondelete="RESTRICT"), nullable=False
    )
    progress_state: Mapped[str] = mapped_column(String(16), nullable=False)
    blocker_code: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
