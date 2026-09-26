from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class MaterialDefinition(Base):
    """Canonical fluid, lubricant, refrigerant, material, or consumable identity."""

    __tablename__ = "material_definitions"
    __table_args__ = (
        CheckConstraint(
            "material_type IN ('engine_oil', 'transmission_fluid', 'gear_oil', 'coolant', "
            "'brake_fluid', 'power_steering_fluid', 'washer_fluid', 'refrigerant', "
            "'grease', 'sealant', 'adhesive', 'cleaner', 'anti_seize', 'threadlocker', "
            "'dielectric_grease', 'penetrant', 'absorbent', 'shop_consumable', 'other')",
            name="ck_material_definitions_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    material_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    material_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    specification: Mapped[str | None] = mapped_column(String(180))
    grade: Mapped[str | None] = mapped_column(String(96))
    family: Mapped[str | None] = mapped_column(String(96))
    is_consumed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    compatibility_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    safety_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    disposal_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    attributes: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class VehicleMaterialApplicability(Base):
    """Exact-configuration compatibility for a material at a physical application point."""

    __tablename__ = "vehicle_material_applicability"
    __table_args__ = (
        CheckConstraint(
            "applicability_state IN ('compatible', 'incompatible', 'conditional')",
            name="ck_vehicle_material_applicability_state",
        ),
        CheckConstraint(
            "material_role IN ('fill', 'lubricant', 'refrigerant_charge', 'cleaning', "
            "'assembly', 'sealing', 'thread_treatment', 'protection', 'consumable', 'other')",
            name="ck_vehicle_material_applicability_role",
        ),
        UniqueConstraint(
            "vehicle_configuration_id",
            "material_definition_id",
            "application_key",
            "material_role",
            "qualifier_key",
            name="uq_vehicle_material_applicability_edge",
        ),
        Index(
            "ix_vehicle_material_app_vehicle",
            "vehicle_configuration_id",
            "applicability_state",
        ),
        Index(
            "ix_vehicle_material_app_material",
            "material_definition_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    vehicle_configuration_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_configurations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    material_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("material_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    vehicle_structure_node_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_structure_nodes.id", ondelete="RESTRICT"),
    )
    application_key: Mapped[str] = mapped_column(String(160), nullable=False)
    material_role: Mapped[str] = mapped_column(String(32), nullable=False)
    applicability_state: Mapped[str] = mapped_column(String(16), nullable=False)
    qualifier_key: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    qualifiers: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class MaterialRequirementBinding(Base):
    """Connects a repair fluid/consumable requirement to canonical material identity."""

    __tablename__ = "material_requirement_bindings"
    __table_args__ = (
        UniqueConstraint(
            "requirement_definition_id",
            name="uq_material_req_bindings_requirement",
        ),
        Index(
            "ix_material_req_bindings_material",
            "material_definition_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    requirement_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("requirement_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    material_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("material_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
