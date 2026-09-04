from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class CatalogCollectionJob(Base):
    __tablename__ = "catalog_collection_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'paused', 'completed', 'failed', 'cancelled')",
            name="ck_catalog_collection_jobs_status",
        ),
        CheckConstraint(
            "cursor_position >= 0 AND total_items >= 0 AND processed_items >= 0 "
            "AND collected_items >= 0 AND verified_items >= 0",
            name="ck_catalog_collection_jobs_nonnegative_counts",
        ),
        Index("ix_catalog_collection_jobs_batch_make_created", "batch_id", "make", "created_at"),
        Index("ix_catalog_collection_jobs_status_created", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("catalog_coverage_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    make: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    cursor_position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    collected_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verified_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_configuration_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_configurations.id", ondelete="SET NULL"),
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CatalogWorkbenchLog(Base):
    __tablename__ = "catalog_workbench_logs"
    __table_args__ = (
        CheckConstraint(
            "level IN ('info', 'warning', 'error')",
            name="ck_catalog_workbench_logs_level",
        ),
        Index("ix_catalog_workbench_logs_job_created", "job_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("catalog_collection_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CatalogWorkbenchSource(Base):
    __tablename__ = "catalog_workbench_sources"
    __table_args__ = (
        CheckConstraint(
            "fetch_status IN ('success', 'failed', 'blocked', 'not_found')",
            name="ck_catalog_workbench_sources_fetch_status",
        ),
        UniqueConstraint(
            "job_id",
            "vehicle_configuration_id",
            "provider",
            name="uq_catalog_workbench_sources_job_vehicle_provider",
        ),
        Index("ix_catalog_workbench_sources_job_created", "job_id", "created_at"),
        Index("ix_catalog_workbench_sources_vehicle", "vehicle_configuration_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("catalog_collection_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    vehicle_configuration_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_configurations.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    fetch_status: Mapped[str] = mapped_column(String(24), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    matched_fields: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    raw_sha256: Mapped[str | None] = mapped_column(String(64))
    cache_path: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
