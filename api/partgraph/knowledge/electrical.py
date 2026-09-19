from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ElectricalDefinition(Base):
    """Canonical physical electrical identity and factual control classification."""

    __tablename__ = "electrical_definitions"
    __table_args__ = (
        CheckConstraint(
            "electrical_type IN ('sensor', 'actuator', 'connector', 'lamp', 'switch', 'fuse', "
            "'relay', 'ground', 'control_module', 'circuit', 'service_interface', 'other')",
            name="ck_electrical_definitions_type",
        ),
        CheckConstraint(
            "control_class IN ('passive', 'sensor_input', 'actuator_output', 'control_module', "
            "'network', 'service_interface', 'high_voltage', 'other')",
            name="ck_electrical_definitions_control_class",
        ),
        UniqueConstraint("id", "electrical_type", name="uq_electrical_definitions_id_type"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    electrical_key: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    electrical_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    control_class: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    attributes: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PhysicalEntityElectrical(Base):
    """Typed electrical node participating in the shared physical graph."""

    __tablename__ = "physical_entity_electrical"
    __table_args__ = (
        CheckConstraint(
            "entity_kind = 'electrical'",
            name="ck_physical_entity_electrical_kind",
        ),
        ForeignKeyConstraint(
            ["entity_id", "entity_kind"],
            ["physical_entities.id", "physical_entities.entity_kind"],
            ondelete="CASCADE",
        ),
    )

    entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    entity_kind: Mapped[str] = mapped_column(
        String(24), nullable=False, default="electrical"
    )
    electrical_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("electrical_definitions.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )


class VehicleElectricalApplicability(Base):
    """Exact-configuration applicability for a physical electrical identity."""

    __tablename__ = "vehicle_electrical_applicability"
    __table_args__ = (
        CheckConstraint(
            "applicability_state IN ('applicable', 'excluded', 'conditional')",
            name="ck_vehicle_electrical_applicability_state",
        ),
        UniqueConstraint(
            "vehicle_configuration_id",
            "electrical_definition_id",
            "application_key",
            "qualifier_key",
            name="uq_vehicle_electrical_applicability_scope",
        ),
        Index(
            "ix_vehicle_electrical_app_vehicle",
            "vehicle_configuration_id",
            "applicability_state",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    vehicle_configuration_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_configurations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    electrical_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("electrical_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    physical_entity_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("physical_entities.id", ondelete="RESTRICT"),
    )
    application_key: Mapped[str] = mapped_column(String(180), nullable=False)
    applicability_state: Mapped[str] = mapped_column(String(16), nullable=False)
    qualifier_key: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    qualifiers: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ConnectorPinDefinition(Base):
    """Physical terminal identity for a canonical connector."""

    __tablename__ = "connector_pin_definitions"
    __table_args__ = (
        CheckConstraint(
            "connector_electrical_type = 'connector'",
            name="ck_connector_pin_definitions_parent_type",
        ),
        ForeignKeyConstraint(
            ["connector_definition_id", "connector_electrical_type"],
            ["electrical_definitions.id", "electrical_definitions.electrical_type"],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "connector_definition_id",
            "pin_key",
            name="uq_connector_pin_definitions_connector_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    connector_definition_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    connector_electrical_type: Mapped[str] = mapped_column(
        String(24), nullable=False, default="connector"
    )
    pin_key: Mapped[str] = mapped_column(String(96), nullable=False)
    pin_label: Mapped[str | None] = mapped_column(String(96))
    circuit_role: Mapped[str | None] = mapped_column(String(96))
    terminal_type: Mapped[str | None] = mapped_column(String(96))
    attributes: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class VehicleElectricalConnection(Base):
    """Exact-configuration pin-to-pin physical electrical connection."""

    __tablename__ = "vehicle_electrical_connections"
    __table_args__ = (
        CheckConstraint(
            "source_pin_id <> target_pin_id",
            name="ck_vehicle_electrical_connections_not_self",
        ),
        CheckConstraint(
            "connection_type IN ('signal', 'power', 'ground', 'control', 'lighting', "
            "'network', 'other')",
            name="ck_vehicle_electrical_connections_type",
        ),
        UniqueConstraint(
            "vehicle_configuration_id",
            "source_pin_id",
            "target_pin_id",
            "connection_type",
            "qualifier_key",
            name="uq_vehicle_electrical_connections_edge",
        ),
        Index(
            "ix_vehicle_electrical_connections_vehicle",
            "vehicle_configuration_id",
            "connection_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    vehicle_configuration_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_configurations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_pin_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("connector_pin_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    target_pin_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("connector_pin_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    connection_type: Mapped[str] = mapped_column(String(16), nullable=False)
    qualifier_key: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    qualifiers: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
