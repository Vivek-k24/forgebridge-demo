"""Add least-privilege, idempotent repair-definition materialization."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0048_repair_materialization"
down_revision: str | None = "0047_conflict_resolution"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MATERIALIZER_ROLE = "partgraph_materializer"
MATERIALIZATION_TABLES = (
    "repair_definitions",
    "repair_operations",
    "requirement_definitions",
    "requirement_uses",
    "requirement_use_evidence",
    "procedure_actions",
    "procedure_action_dependencies",
    "procedure_action_requirement_uses",
    "procedure_action_evidence",
    "canonical_record_versions",
    "canonical_record_evidence",
)


def _ensure_role() -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_roles WHERE rolname = '{MATERIALIZER_ROLE}'
                ) THEN
                    CREATE ROLE {MATERIALIZER_ROLE} NOLOGIN;
                END IF;
            END
            $$
            """
        )
    )
    op.execute(
        sa.text(
            f"GRANT {MATERIALIZER_ROLE} TO CURRENT_USER WITH INHERIT FALSE, SET TRUE"
        )
    )


def upgrade() -> None:
    _ensure_role()
    op.add_column(
        "canonical_record_versions",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "canonical_record_versions",
        sa.Column("request_sha256", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_canonical_record_versions_idempotency_key",
        "canonical_record_versions",
        ["idempotency_key"],
    )

    # One verified-evidence snapshot may legitimately support more than one
    # normalized claim in the same canonical publication.
    op.drop_constraint(
        "uq_canonical_record_evidence_pair",
        "canonical_record_evidence",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_canonical_record_evidence_claim",
        "canonical_record_evidence",
        ["record_version_id", "verified_evidence_id", "mechanical_claim_id"],
    )
    op.create_index(
        "uq_canonical_record_evidence_evidence_only",
        "canonical_record_evidence",
        ["record_version_id", "verified_evidence_id"],
        unique=True,
        postgresql_where=sa.text("mechanical_claim_id IS NULL"),
    )

    # The service serializes this scope too, but correctness does not depend on
    # application locking alone.
    op.create_index(
        "uq_repair_definitions_current_verified",
        "repair_definitions",
        ["vehicle_configuration_id", "repair_key"],
        unique=True,
        postgresql_where=sa.text("status = 'verified'"),
    )

    tables = ", ".join(f"public.{table}" for table in MATERIALIZATION_TABLES)
    op.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {MATERIALIZER_ROLE}"))
    op.execute(sa.text(f"GRANT SELECT ON {tables} TO {MATERIALIZER_ROLE}"))
    op.execute(
        sa.text(
            "GRANT SELECT ON public.catalog_sources, public.vehicle_configurations, "
            "public.mechanical_claims, public.canonical_conflicts, "
            f"public.repair_capability_policies TO {MATERIALIZER_ROLE}"
        )
    )
    op.execute(sa.text(f"GRANT INSERT ON {tables} TO {MATERIALIZER_ROLE}"))

    # Published child rows remain append-only. The materializer may transition
    # only the previous version envelopes into their superseded state.
    op.execute(
        sa.text(
            "GRANT UPDATE (status, superseded_by_id) ON public.repair_definitions "
            f"TO {MATERIALIZER_ROLE}"
        )
    )
    op.execute(
        sa.text(
            "GRANT UPDATE (publication_state) ON public.canonical_record_versions "
            f"TO {MATERIALIZER_ROLE}"
        )
    )
    op.execute(sa.text(f"REVOKE DELETE ON {tables} FROM {MATERIALIZER_ROLE}"))


def downgrade() -> None:
    tables = ", ".join(f"public.{table}" for table in MATERIALIZATION_TABLES)
    op.execute(sa.text(f"REVOKE INSERT ON {tables} FROM {MATERIALIZER_ROLE}"))
    op.execute(
        sa.text(
            "REVOKE UPDATE (publication_state) ON public.canonical_record_versions "
            f"FROM {MATERIALIZER_ROLE}"
        )
    )
    op.execute(
        sa.text(
            "REVOKE UPDATE (status, superseded_by_id) ON public.repair_definitions "
            f"FROM {MATERIALIZER_ROLE}"
        )
    )
    op.execute(
        sa.text(
            "REVOKE SELECT ON public.catalog_sources, public.vehicle_configurations, "
            "public.mechanical_claims, public.canonical_conflicts, "
            f"public.repair_capability_policies FROM {MATERIALIZER_ROLE}"
        )
    )
    op.execute(sa.text(f"REVOKE SELECT ON {tables} FROM {MATERIALIZER_ROLE}"))
    op.execute(sa.text(f"REVOKE USAGE ON SCHEMA public FROM {MATERIALIZER_ROLE}"))

    op.drop_index(
        "uq_repair_definitions_current_verified",
        table_name="repair_definitions",
    )
    op.drop_index(
        "uq_canonical_record_evidence_evidence_only",
        table_name="canonical_record_evidence",
    )
    op.drop_constraint(
        "uq_canonical_record_evidence_claim",
        "canonical_record_evidence",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_canonical_record_evidence_pair",
        "canonical_record_evidence",
        ["record_version_id", "verified_evidence_id"],
    )
    op.drop_constraint(
        "uq_canonical_record_versions_idempotency_key",
        "canonical_record_versions",
        type_="unique",
    )
    op.drop_column("canonical_record_versions", "request_sha256")
    op.drop_column("canonical_record_versions", "idempotency_key")
    op.execute(sa.text(f"REVOKE {MATERIALIZER_ROLE} FROM CURRENT_USER"))
    op.execute(sa.text(f"DROP ROLE IF EXISTS {MATERIALIZER_ROLE}"))
