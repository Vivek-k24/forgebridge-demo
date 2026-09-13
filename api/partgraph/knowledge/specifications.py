from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class SpecificationDefinition(Base):
    """Reusable identity for a measurable automotive specification or limit."""

    __tablename__ = "specification_definitions"
    __table_args__ = (
        CheckConstraint(
            "specification_type IN ('torque', 'pressure', 'flow', 'clearance', 'dimension', "
            "'capacity', 'service_limit', 'electrical', 'temperature', 'speed', 'time', "
            "'mass', 'volume', 'ratio', 'other')",
            name="ck_specification_definitions_type",
        ),
        CheckConstraint(
            "value_kind IN ('scalar', 'range', 'maximum', 'minimum', 'text')",
            name="ck_specification_definitions_value_kind",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    specification_key: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    specification_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    value_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    quantity_kind: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class VehicleSpecificationValue(Base):
    """Exact-configuration value, range, capacity, or service limit."""

    __tablename__ = "vehicle_specification_values"
    __table_args__ = (
        CheckConstraint(
            "nominal_value IS NOT NULL OR minimum_value IS NOT NULL OR maximum_value IS NOT NULL "
            "OR text_value IS NOT NULL",
            name="ck_vehicle_spec_values_has_value",
        ),
        CheckConstraint(
            "minimum_value IS NULL OR maximum_value IS NULL OR minimum_value <= maximum_value",
            name="ck_vehicle_spec_values_range",
        ),
        UniqueConstraint(
            "vehicle_configuration_id",
            "specification_definition_id",
            "application_key",
            "qualifier_key",
            name="uq_vehicle_spec_values_scope",
        ),
        Index(
            "ix_vehicle_spec_values_vehicle",
            "vehicle_configuration_id",
            "specification_definition_id",
        ),
        Index(
            "ix_vehicle_spec_values_entity",
            "physical_entity_id",
        ),
        Index(
            "ix_vehicle_spec_values_material",
            "material_definition_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    vehicle_configuration_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_configurations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    specification_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("specification_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    physical_entity_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("physical_entities.id", ondelete="RESTRICT"),
    )
    material_definition_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("material_definitions.id", ondelete="RESTRICT"),
    )
    application_key: Mapped[str] = mapped_column(String(180), nullable=False)
    nominal_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    minimum_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    maximum_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    unit: Mapped[str | None] = mapped_column(String(48))
    text_value: Mapped[str | None] = mapped_column(String(255))
    qualifier_key: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    conditions: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
