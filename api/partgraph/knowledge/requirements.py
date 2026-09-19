from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ToolEquipmentDefinition(Base):
    """Canonical reusable tool/equipment identity, separate from procedure support policy."""

    __tablename__ = "tool_equipment_definitions"
    __table_args__ = (
        CheckConstraint(
            "resource_type IN ('hand_tool', 'power_tool', 'specialty_tool', "
            "'lifting_support', 'measuring_diagnostic', 'fluid_service', "
            "'safety_equipment', 'shop_equipment', 'professional_equipment', 'other')",
            name="ck_tool_equipment_definitions_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    resource_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    specifications: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class WorkspaceDefinition(Base):
    """Canonical physical workspace prerequisite for a repair or operation."""

    __tablename__ = "workspace_definitions"
    __table_args__ = (
        CheckConstraint(
            "workspace_type IN ('surface', 'clearance', 'ventilation', 'lighting', "
            "'weather_protection', 'lifting_access', 'fluid_containment', 'power_supply', "
            "'compressed_air', 'fire_safety', 'cleanliness', 'other')",
            name="ck_workspace_definitions_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    workspace_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    specifications: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ToolEquipmentRequirementBinding(Base):
    __tablename__ = "tool_equipment_requirement_bindings"
    __table_args__ = (
        UniqueConstraint(
            "requirement_definition_id",
            name="uq_tool_req_bindings_requirement",
        ),
        Index(
            "ix_tool_req_bindings_tool_id",
            "tool_equipment_definition_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    requirement_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("requirement_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    tool_equipment_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tool_equipment_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class WorkspaceRequirementBinding(Base):
    __tablename__ = "workspace_requirement_bindings"
    __table_args__ = (
        UniqueConstraint(
            "requirement_definition_id",
            name="uq_workspace_req_bindings_requirement",
        ),
        Index(
            "ix_workspace_req_bindings_workspace_id",
            "workspace_definition_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    requirement_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("requirement_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace_definition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspace_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
