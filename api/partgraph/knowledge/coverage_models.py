from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class CatalogCoverageBatch(Base):
    """Named collection/verification batch surfaced by the coverage dashboard."""

    __tablename__ = "catalog_coverage_batches"
    __table_args__ = (
        CheckConstraint("target_rows >= 1", name="ck_catalog_coverage_batches_target_rows"),
        CheckConstraint(
            "status IN ('collecting', 'verifying', 'verified', 'superseded')",
            name="ck_catalog_coverage_batches_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    batch_key: Mapped[str] = mapped_column(String(96), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(180), nullable=False)
    target_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    verification_rule: Mapped[str] = mapped_column(String(96), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="collecting")
    scope: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CatalogCoverageItem(Base):
    """One canonical configuration candidate tracked inside a coverage batch."""

    __tablename__ = "catalog_coverage_items"
    __table_args__ = (
        CheckConstraint(
            "source_match_count >= 0",
            name="ck_catalog_coverage_items_source_match_count",
        ),
        CheckConstraint(
            "verification_status IN ('unverified', 'verified', 'conflict')",
            name="ck_catalog_coverage_items_verification_status",
        ),
        UniqueConstraint(
            "batch_id",
            "vehicle_configuration_id",
            name="uq_catalog_coverage_items_batch_vehicle",
        ),
        Index("ix_catalog_coverage_items_batch_status", "batch_id", "verification_status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("catalog_coverage_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vehicle_configuration_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_configurations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    verification_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="unverified"
    )
    source_match_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    source_matrix: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
