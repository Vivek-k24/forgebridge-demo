from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class VehicleStructureNode(Base):
    """Configuration-specific system/assembly node in the canonical physical hierarchy."""

    __tablename__ = "vehicle_structure_nodes"
    __table_args__ = (
        CheckConstraint(
            "node_type IN ('system', 'subsystem', 'assembly', 'subassembly')",
            name="ck_vehicle_structure_nodes_type",
        ),
        CheckConstraint(
            "position >= 0",
            name="ck_vehicle_structure_nodes_position",
        ),
        CheckConstraint(
            "parent_node_id IS NULL OR parent_node_id <> id",
            name="ck_vehicle_structure_nodes_not_self_parent",
        ),
        UniqueConstraint(
            "vehicle_configuration_id",
            "node_key",
            name="uq_vehicle_structure_nodes_vehicle_key",
        ),
        Index(
            "ix_vehicle_structure_nodes_vehicle_parent_position",
            "vehicle_configuration_id",
            "parent_node_id",
            "position",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    vehicle_configuration_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_configurations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    node_key: Mapped[str] = mapped_column(String(160), nullable=False)
    node_type: Mapped[str] = mapped_column(String(24), nullable=False)
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    parent_node_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_structure_nodes.id", ondelete="RESTRICT"),
        index=True,
    )
    placement: Mapped[str | None] = mapped_column(String(96))
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
