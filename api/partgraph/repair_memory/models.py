from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class RepairStorageLocation(Base):
    __tablename__ = "repair_storage_locations"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repair_sessions.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RepairFastener(Base):
    __tablename__ = "repair_fasteners"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repair_sessions.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    origin: Mapped[str | None] = mapped_column(String(160))
    position: Mapped[str | None] = mapped_column(String(160))
    physical_state: Mapped[str] = mapped_column(String(16), nullable=False)
    storage_location_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repair_storage_locations.id", ondelete="SET NULL"),
    )
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class RepairInventoryItem(Base):
    __tablename__ = "repair_inventory_items"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repair_sessions.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    procurement_state: Mapped[str] = mapped_column(String(16), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(160))
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class RepairObservation(Base):
    __tablename__ = "repair_observations"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repair_sessions.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str] = mapped_column(String(1000), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    review_state: Mapped[str] = mapped_column(String(16), nullable=False)
    fastener_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repair_fasteners.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RepairPhotoEvidence(Base):
    __tablename__ = "repair_photo_evidence"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repair_sessions.id", ondelete="CASCADE"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    observation_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repair_observations.id", ondelete="SET NULL")
    )
    fastener_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repair_fasteners.id", ondelete="SET NULL")
    )
    storage_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(32), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
