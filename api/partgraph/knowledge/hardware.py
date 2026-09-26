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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class HardwareDefinition(Base):
    """Canonical identity and physical properties for small repair hardware."""

    __tablename__ = "hardware_definitions"
    __table_args__ = (
        CheckConstraint(
            "hardware_type IN ('bolt', 'nut', 'screw', 'stud', 'washer', 'clip', "
            "'rivet', 'pin', 'clamp', 'seal', 'gasket', 'o_ring', 'retainer', "
            "'cotter_pin', 'spacer', 'spring', 'plug', 'other')",
            name="ck_hardware_definitions_type",
        ),
        CheckConstraint(
            "reuse_policy IN ('unknown', 'reusable', 'replace_if_damaged', 'single_use')",
            name="ck_hardware_definitions_reuse_policy",
        ),
        CheckConstraint(
            "nominal_diameter_mm IS NULL OR nominal_diameter_mm > 0",
            name="ck_hardware_definitions_nominal_diameter",
        ),
        CheckConstraint(
            "length_mm IS NULL OR length_mm > 0",
            name="ck_hardware_definitions_length",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    hardware_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    hardware_type: Mapped[str] = mapped_column(String(24), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    nominal_size: Mapped[str | None] = mapped_column(String(96))
    thread_spec: Mapped[str | None] = mapped_column(String(64))
    nominal_diameter_mm: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    length_mm: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    drive_type: Mapped[str | None] = mapped_column(String(64))
    head_style: Mapped[str | None] = mapped_column(String(64))
    material: Mapped[str | None] = mapped_column(String(96))
    reuse_policy: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="unknown",
        server_default=text("'unknown'"),
    )
    attributes: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class HardwarePartIdentity(Base):
    """Maps zero or more manufacturer/OEM part identities onto canonical hardware."""

    __tablename__ = "hardware_part_identities"
    __table_args__ = (
        UniqueConstraint(
            "hardware_definition_id",
            "part_identity_id",
            name="uq_hardware_part_identities_mapping",
        ),
        UniqueConstraint(
            "part_identity_id",
            name="uq_hardware_part_identities_part",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    hardware_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("hardware_definitions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    part_identity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("part_identities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
