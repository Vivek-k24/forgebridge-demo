from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class VehicleConfiguration(Base):
    __tablename__ = "vehicle_configurations"
    __table_args__ = (
        CheckConstraint(
            "year >= 1996 AND year <= 2100",
            name="ck_vehicle_configurations_year",
        ),
        Index(
            "ix_vehicle_configurations_selection",
            "market",
            "year",
            "make",
            "model",
            "trim",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    identity_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    base_identity_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    canonicalization_version: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=2,
    )
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    make: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(96), nullable=False)
    generation: Mapped[str | None] = mapped_column(String(96))
    trim: Mapped[str | None] = mapped_column(String(128))
    body_style: Mapped[str | None] = mapped_column(String(64))
    engine: Mapped[str | None] = mapped_column(String(128))
    transmission: Mapped[str | None] = mapped_column(String(128))
    drivetrain: Mapped[str | None] = mapped_column(String(64))
    identity_source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    verification_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unverified",
    )
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


class VehicleSpecificationProfile(Base):
    __tablename__ = "vehicle_specification_profiles"
    __table_args__ = (
        CheckConstraint(
            "profile_version >= 1",
            name="ck_vehicle_specification_profiles_version",
        ),
        CheckConstraint(
            "source_match_count >= 1",
            name="ck_vehicle_specification_profiles_source_match_count",
        ),
        CheckConstraint(
            "verification_status IN ('candidate', 'verified', 'superseded')",
            name="ck_vehicle_specification_profiles_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    vehicle_configuration_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_configurations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    profile_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_match_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    profile: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    source_matrix: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
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
