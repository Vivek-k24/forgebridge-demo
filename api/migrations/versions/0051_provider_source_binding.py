"""Persist trusted provider-to-source bindings and add a least-privilege ingestor role."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0051_provider_source_binding"
down_revision: str | None = "0050_claim_authority_policy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INGESTOR_ROLE = "partgraph_ingestor"
STAGING_SCHEMA = "catalog_staging"


def _ensure_role(role: str) -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                    CREATE ROLE {role} NOLOGIN;
                END IF;
            END
            $$
            """
        )
    )
    op.execute(sa.text(f"GRANT {role} TO CURRENT_USER WITH INHERIT FALSE, SET TRUE"))


def upgrade() -> None:
    op.create_table(
        "provider_source_bindings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_connection_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["provider_connection_id"],
            ["provider_connections.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["catalog_sources.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_connection_id",
            "source_id",
            name="uq_provider_source_bindings_pair",
        ),
    )
    op.create_index(
        "ix_provider_source_bindings_provider_connection_id",
        "provider_source_bindings",
        ["provider_connection_id"],
        unique=False,
    )
    op.create_index(
        "ix_provider_source_bindings_source_id",
        "provider_source_bindings",
        ["source_id"],
        unique=False,
    )

    op.execute(sa.text("REVOKE ALL ON public.provider_source_bindings FROM PUBLIC"))
    # Operator/admin application code manages bindings. A disabled binding is the safe default.
    op.execute(
        sa.text(
            "GRANT SELECT, INSERT, UPDATE ON public.provider_source_bindings TO partgraph_app"
        )
    )

    _ensure_role(INGESTOR_ROLE)
    op.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {INGESTOR_ROLE}"))
    op.execute(sa.text(f"GRANT USAGE ON SCHEMA {STAGING_SCHEMA} TO {INGESTOR_ROLE}"))
    op.execute(
        sa.text(
            f"GRANT SELECT ON public.provider_connections, public.provider_source_bindings, "
            f"public.catalog_sources, public.vehicle_configurations TO {INGESTOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"GRANT SELECT ON {STAGING_SCHEMA}.ingestion_batches, "
            f"{STAGING_SCHEMA}.source_records TO {INGESTOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"GRANT INSERT ON {STAGING_SCHEMA}.ingestion_batches, "
            f"{STAGING_SCHEMA}.source_records TO {INGESTOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"GRANT UPDATE (status, completed_at) ON {STAGING_SCHEMA}.ingestion_batches "
            f"TO {INGESTOR_ROLE}"
        )
    )

    # Acquisition can never review, verify, publish claims, or change canonical truth.
    protected_tables = (
        "catalog_verified_evidence, mechanical_claims, canonical_record_versions, "
        "canonical_record_evidence, canonical_conflicts, canonical_conflict_items, "
        "source_authority_policies, repair_definitions, repair_operations, "
        "requirement_definitions, requirement_uses, procedure_actions"
    )
    op.execute(
        sa.text(
            f"REVOKE INSERT, UPDATE, DELETE ON public.{protected_tables.replace(', ', ', public.')} "
            f"FROM {INGESTOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"REVOKE INSERT, UPDATE, DELETE ON public.provider_connections, "
            f"public.provider_source_bindings, public.catalog_sources, "
            f"public.vehicle_configurations FROM {INGESTOR_ROLE}"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            f"REVOKE ALL PRIVILEGES ON {STAGING_SCHEMA}.source_records FROM {INGESTOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"REVOKE ALL PRIVILEGES ON {STAGING_SCHEMA}.ingestion_batches FROM {INGESTOR_ROLE}"
        )
    )
    op.execute(sa.text(f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {INGESTOR_ROLE}"))
    op.execute(sa.text(f"REVOKE USAGE ON SCHEMA {STAGING_SCHEMA} FROM {INGESTOR_ROLE}"))
    op.execute(sa.text(f"REVOKE USAGE ON SCHEMA public FROM {INGESTOR_ROLE}"))
    op.execute(sa.text(f"REVOKE {INGESTOR_ROLE} FROM CURRENT_USER"))
    op.execute(sa.text(f"DROP ROLE IF EXISTS {INGESTOR_ROLE}"))
    op.drop_index(
        "ix_provider_source_bindings_source_id",
        table_name="provider_source_bindings",
    )
    op.drop_index(
        "ix_provider_source_bindings_provider_connection_id",
        table_name="provider_source_bindings",
    )
    op.drop_table("provider_source_bindings")
