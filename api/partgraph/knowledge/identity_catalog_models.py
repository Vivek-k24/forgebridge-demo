from __future__ import annotations

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
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class CatalogIdentityModel(Base):
    __tablename__ = "catalog_identity_models"
    __table_args__ = (
        CheckConstraint(
            "year >= 1996 AND year <= 2100",
            name="ck_catalog_identity_models_year",
        ),
        CheckConstraint(
            "status IN ('discovered', 'corroborated')",
            name="ck_catalog_identity_models_status",
        ),
        CheckConstraint(
            "source_count >= 1",
            name="ck_catalog_identity_models_source_count",
        ),
        UniqueConstraint(
            "market",
            "year",
            "make_key",
            "model_key",
            name="uq_catalog_identity_models_selection",
        ),
        Index(
            "ix_catalog_identity_models_selection",
            "market",
            "year",
            "make",
            "model",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    market: Mapped[str] = mapped_column(String(16), nullable=False, default="US")
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    make: Mapped[str] = mapped_column(String(64), nullable=False)
    make_key: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    model_key: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="discovered")
    source_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    sources: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CatalogIdentityTrim(Base):
    __tablename__ = "catalog_identity_trims"
    __table_args__ = (
        CheckConstraint(
            "status IN ('discovered', 'corroborated')",
            name="ck_catalog_identity_trims_status",
        ),
        CheckConstraint(
            "source_count >= 1",
            name="ck_catalog_identity_trims_source_count",
        ),
        UniqueConstraint(
            "model_id",
            "trim_key",
            name="uq_catalog_identity_trims_model_trim",
        ),
        Index("ix_catalog_identity_trims_model", "model_id", "trim"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    model_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("catalog_identity_models.id", ondelete="CASCADE"),
        nullable=False,
    )
    trim: Mapped[str] = mapped_column(String(160), nullable=False)
    trim_key: Mapped[str] = mapped_column(String(192), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="discovered")
    source_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    sources: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CatalogIdentityProgress(Base):
    __tablename__ = "catalog_identity_progress"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_catalog_identity_progress_status",
        ),
        CheckConstraint(
            "models_found >= 0 AND trims_found >= 0",
            name="ck_catalog_identity_progress_counts",
        ),
        UniqueConstraint("make", "year", name="uq_catalog_identity_progress_make_year"),
        Index("ix_catalog_identity_progress_status", "status", "make", "year"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    make: Mapped[str] = mapped_column(String(64), nullable=False)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    models_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trims_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_summary: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
