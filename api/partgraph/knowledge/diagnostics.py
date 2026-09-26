from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
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


class DiagnosticSignalDefinition(Base):
    """Reusable symptom or diagnostic trouble-code identity."""

    __tablename__ = "diagnostic_signal_definitions"
    __table_args__ = (
        CheckConstraint(
            "signal_type IN ('symptom', 'dtc')",
            name="ck_diagnostic_signal_definitions_type",
        ),
        CheckConstraint(
            "(signal_type = 'dtc' AND code IS NOT NULL AND code_system IS NOT NULL) OR "
            "(signal_type = 'symptom' AND code IS NULL AND code_system IS NULL)",
            name="ck_diagnostic_signal_definitions_code_scope",
        ),
        CheckConstraint(
            "code_system IS NULL OR code_system IN ('obd2', 'manufacturer', 'other')",
            name="ck_diagnostic_signal_definitions_code_system",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    signal_key: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    signal_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    code: Mapped[str | None] = mapped_column(String(24))
    code_system: Mapped[str | None] = mapped_column(String(24))
    family: Mapped[str | None] = mapped_column(String(64))
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class VehicleDiagnosticSignal(Base):
    """Exact-configuration applicability for a symptom or DTC signal."""

    __tablename__ = "vehicle_diagnostic_signals"
    __table_args__ = (
        CheckConstraint(
            "applicability_state IN ('applicable', 'excluded', 'conditional')",
            name="ck_vehicle_diagnostic_signals_state",
        ),
        UniqueConstraint(
            "vehicle_configuration_id",
            "signal_definition_id",
            "application_key",
            "qualifier_key",
            name="uq_vehicle_diagnostic_signals_scope",
        ),
        Index(
            "ix_vehicle_diagnostic_signals_vehicle",
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
    signal_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("diagnostic_signal_definitions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
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
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class DiagnosticInspectionDefinition(Base):
    """Reusable inspection identity; measurements reuse canonical specification definitions."""

    __tablename__ = "diagnostic_inspection_definitions"
    __table_args__ = (
        CheckConstraint(
            "inspection_type IN ('visual', 'functional', 'measurement', 'leak', 'pressure', "
            "'electrical', 'continuity', 'other')",
            name="ck_diagnostic_inspection_definitions_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    inspection_key: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    inspection_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    specification_definition_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("specification_definitions.id", ondelete="RESTRICT"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class VehicleDiagnosticInspection(Base):
    """Exact-configuration inspection with optional expected measurement/result."""

    __tablename__ = "vehicle_diagnostic_inspections"
    __table_args__ = (
        UniqueConstraint(
            "vehicle_configuration_id",
            "inspection_definition_id",
            "application_key",
            "qualifier_key",
            name="uq_vehicle_diagnostic_inspections_scope",
        ),
        Index(
            "ix_vehicle_diagnostic_inspections_vehicle",
            "vehicle_configuration_id",
            "inspection_definition_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    vehicle_configuration_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_configurations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    inspection_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("diagnostic_inspection_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    physical_entity_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("physical_entities.id", ondelete="RESTRICT"),
    )
    expected_specification_value_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_specification_values.id", ondelete="RESTRICT"),
    )
    application_key: Mapped[str] = mapped_column(String(180), nullable=False)
    expected_result_text: Mapped[str | None] = mapped_column(String(500))
    qualifier_key: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    qualifiers: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class DiagnosticCauseRelationship(Base):
    """Exact-configuration suspected/confirmed relationship from a signal to a physical cause."""

    __tablename__ = "diagnostic_cause_relationships"
    __table_args__ = (
        CheckConstraint(
            "cause_state IN ('suspected', 'confirmed', 'excluded')",
            name="ck_diagnostic_cause_relationships_state",
        ),
        UniqueConstraint(
            "vehicle_configuration_id",
            "vehicle_diagnostic_signal_id",
            "target_physical_entity_id",
            "qualifier_key",
            name="uq_diagnostic_cause_relationships_edge",
        ),
        Index(
            "ix_diagnostic_cause_relationships_vehicle_state",
            "vehicle_configuration_id",
            "cause_state",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    vehicle_configuration_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_configurations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    vehicle_diagnostic_signal_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_diagnostic_signals.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_physical_entity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("physical_entities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    cause_state: Mapped[str] = mapped_column(String(16), nullable=False)
    qualifier_key: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    rationale: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
