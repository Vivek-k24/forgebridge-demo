"""Add the typed physical/mechanical relationship graph."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0037_physical_relationship_graph"
down_revision: str | None = "0036_part_interchange"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"
REVIEWER_ROLE = "partgraph_reviewer"
SHARED_TABLES = (
    "physical_entities, physical_entity_structure_nodes, physical_entity_components, "
    "physical_entity_parts, physical_relationships"
)


def upgrade() -> None:
    op.create_table(
        "physical_entities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_kind", sa.String(length=24), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "entity_kind IN ('structure_node', 'component', 'part', 'hardware', 'electrical')",
            name="ck_physical_entities_kind",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "entity_kind", name="uq_physical_entities_id_kind"),
    )

    op.create_table(
        "physical_entity_structure_nodes",
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column(
            "entity_kind",
            sa.String(length=24),
            nullable=False,
            server_default="structure_node",
        ),
        sa.Column("structure_node_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "entity_kind = 'structure_node'",
            name="ck_physical_entity_structure_nodes_kind",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id", "entity_kind"],
            ["physical_entities.id", "physical_entities.entity_kind"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["structure_node_id"],
            ["vehicle_structure_nodes.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("entity_id"),
        sa.UniqueConstraint("structure_node_id"),
    )

    op.create_table(
        "physical_entity_components",
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column(
            "entity_kind",
            sa.String(length=24),
            nullable=False,
            server_default="component",
        ),
        sa.Column("component_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "entity_kind = 'component'",
            name="ck_physical_entity_components_kind",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id", "entity_kind"],
            ["physical_entities.id", "physical_entities.entity_kind"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["component_id"],
            ["component_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("entity_id"),
        sa.UniqueConstraint("component_id"),
    )

    op.create_table(
        "physical_entity_parts",
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column(
            "entity_kind",
            sa.String(length=24),
            nullable=False,
            server_default="part",
        ),
        sa.Column("part_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "entity_kind = 'part'",
            name="ck_physical_entity_parts_kind",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id", "entity_kind"],
            ["physical_entities.id", "physical_entities.entity_kind"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["part_id"],
            ["part_identities.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("entity_id"),
        sa.UniqueConstraint("part_id"),
    )

    op.create_table(
        "physical_relationships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("source_entity_id", sa.Uuid(), nullable=False),
        sa.Column("target_entity_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_type", sa.String(length=32), nullable=False),
        sa.Column(
            "qualifier_key",
            sa.String(length=128),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "qualifiers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "relationship_type IN ('contains', 'attached_to', 'sealed_by', 'fastened_by', "
            "'fluid_connected_to', 'electrically_connected_to', 'remove_before', 'related_to')",
            name="ck_physical_relationships_type",
        ),
        sa.CheckConstraint(
            "source_entity_id <> target_entity_id",
            name="ck_physical_relationships_distinct_entities",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_configuration_id"],
            ["vehicle_configurations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_entity_id"],
            ["physical_entities.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_entity_id"],
            ["physical_entities.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "vehicle_configuration_id",
            "source_entity_id",
            "target_entity_id",
            "relationship_type",
            "qualifier_key",
            name="uq_physical_relationships_edge",
        ),
    )
    op.create_index(
        "ix_physical_relationships_vehicle_configuration_id",
        "physical_relationships",
        ["vehicle_configuration_id"],
    )
    op.create_index(
        "ix_physical_relationships_source_entity_id",
        "physical_relationships",
        ["source_entity_id"],
    )
    op.create_index(
        "ix_physical_relationships_vehicle_type",
        "physical_relationships",
        ["vehicle_configuration_id", "relationship_type"],
    )
    op.create_index(
        "ix_physical_relationships_target_type",
        "physical_relationships",
        ["target_entity_id", "relationship_type"],
    )

    op.execute(sa.text(f"GRANT SELECT ON {SHARED_TABLES} TO {APP_ROLE}, {REVIEWER_ROLE}"))
    op.execute(
        sa.text(
            f"REVOKE INSERT, UPDATE, DELETE ON {SHARED_TABLES} FROM {APP_ROLE}, {REVIEWER_ROLE}"
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"REVOKE SELECT ON {SHARED_TABLES} FROM {APP_ROLE}, {REVIEWER_ROLE}"))
    op.drop_index("ix_physical_relationships_target_type", table_name="physical_relationships")
    op.drop_index("ix_physical_relationships_vehicle_type", table_name="physical_relationships")
    op.drop_index("ix_physical_relationships_source_entity_id", table_name="physical_relationships")
    op.drop_index(
        "ix_physical_relationships_vehicle_configuration_id",
        table_name="physical_relationships",
    )
    op.drop_table("physical_relationships")
    op.drop_table("physical_entity_parts")
    op.drop_table("physical_entity_components")
    op.drop_table("physical_entity_structure_nodes")
    op.drop_table("physical_entities")
