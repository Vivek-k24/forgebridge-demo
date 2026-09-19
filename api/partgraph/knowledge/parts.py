from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ComponentDefinition(Base):
    """Canonical semantic identity for a serviceable physical component."""

    __tablename__ = "component_definitions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    component_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class PartIdentity(Base):
    """Manufacturer/part-number identity independent of vehicle fitment."""

    __tablename__ = "part_identities"
    __table_args__ = (
        UniqueConstraint(
            "manufacturer",
            "part_number",
            "revision",
            name="uq_part_identities_manufacturer_number_revision",
        ),
        Index("ix_part_identities_part_number", "part_number"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    manufacturer: Mapped[str] = mapped_column(String(96), nullable=False)
    part_number: Mapped[str] = mapped_column(String(96), nullable=False)
    revision: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ComponentPartRole(Base):
    """Associates a physical part identity with its canonical component role/position."""

    __tablename__ = "component_part_roles"
    __table_args__ = (
        UniqueConstraint(
            "component_id",
            "part_id",
            "position_key",
            name="uq_component_part_roles_component_part_position",
        ),
        Index("ix_component_part_roles_part_id", "part_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    component_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("component_definitions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    part_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("part_identities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    position_key: Mapped[str] = mapped_column(String(96), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
