from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, String, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class PhysicalEntity(Base):
    """Typed registry node used by the canonical physical relationship graph."""

    __tablename__ = "physical_entities"
    __table_args__ = (
        CheckConstraint(
            "entity_kind IN ('structure_node', 'component', 'part', 'hardware', 'electrical')",
            name="ck_physical_entities_kind",
        ),
        UniqueConstraint("id", "entity_kind", name="uq_physical_entities_id_kind"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    entity_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class PhysicalEntityStructureNode(Base):
    __tablename__ = "physical_entity_structure_nodes"
    __table_args__ = (
        CheckConstraint(
            "entity_kind = 'structure_node'",
            name="ck_physical_entity_structure_nodes_kind",
        ),
        ForeignKeyConstraint(
            ["entity_id", "entity_kind"],
            ["physical_entities.id", "physical_entities.entity_kind"],
            ondelete="CASCADE",
        ),
    )

    entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    entity_kind: Mapped[str] = mapped_column(
        String(24), nullable=False, default="structure_node"
    )
    structure_node_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_structure_nodes.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )


class PhysicalEntityComponent(Base):
    __tablename__ = "physical_entity_components"
    __table_args__ = (
        CheckConstraint(
            "entity_kind = 'component'",
            name="ck_physical_entity_components_kind",
        ),
        ForeignKeyConstraint(
            ["entity_id", "entity_kind"],
            ["physical_entities.id", "physical_entities.entity_kind"],
            ondelete="CASCADE",
        ),
    )

    entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    entity_kind: Mapped[str] = mapped_column(String(24), nullable=False, default="component")
    component_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("component_definitions.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )


class PhysicalEntityPart(Base):
    __tablename__ = "physical_entity_parts"
    __table_args__ = (
        CheckConstraint(
            "entity_kind = 'part'",
            name="ck_physical_entity_parts_kind",
        ),
        ForeignKeyConstraint(
            ["entity_id", "entity_kind"],
            ["physical_entities.id", "physical_entities.entity_kind"],
            ondelete="CASCADE",
        ),
    )

    entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    entity_kind: Mapped[str] = mapped_column(String(24), nullable=False, default="part")
    part_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("part_identities.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )


class PhysicalRelationship(Base):
    """Configuration-scoped edge between typed physical entities."""

    __tablename__ = "physical_relationships"
    __table_args__ = (
        CheckConstraint(
            "relationship_type IN ('contains', 'attached_to', 'sealed_by', 'fastened_by', "
            "'fluid_connected_to', 'electrically_connected_to', 'remove_before', 'related_to')",
            name="ck_physical_relationships_type",
        ),
        CheckConstraint(
            "source_entity_id <> target_entity_id",
            name="ck_physical_relationships_distinct_entities",
        ),
        UniqueConstraint(
            "vehicle_configuration_id",
            "source_entity_id",
            "target_entity_id",
            "relationship_type",
            "qualifier_key",
            name="uq_physical_relationships_edge",
        ),
        Index(
            "ix_physical_relationships_vehicle_type",
            "vehicle_configuration_id",
            "relationship_type",
        ),
        Index(
            "ix_physical_relationships_target_type",
            "target_entity_id",
            "relationship_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    vehicle_configuration_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_configurations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_entity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("physical_entities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    target_entity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("physical_entities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    relationship_type: Mapped[str] = mapped_column(String(32), nullable=False)
    qualifier_key: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    qualifiers: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
