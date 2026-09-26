"""Repair legacy 0045 history and add least-privilege Phase 6 actor roles."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0046_pipeline_actor_roles"
down_revision: str | None = "0045_provenance_conflicts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"
REVIEWER_ROLE = "partgraph_reviewer"
CONTRIBUTOR_ROLE = "partgraph_contributor"
CURATOR_ROLE = "partgraph_curator"
STAGING_SCHEMA = "catalog_staging"
DOMAIN_CHECK = (
    "('vehicle_identity', 'structure', 'part_identity', 'fitment', 'interchange', "
    "'physical_relationship', 'hardware', 'requirement', 'material', 'specification', "
    "'repair', 'procedure', 'downstream', 'diagnostic', 'electrical', 'capability')"
)
SOURCE_CLASS_CHECK = (
    "('government', 'oem_service', 'licensed_oem_derived', 'oem_parts', "
    "'industry_standard', 'retailer', 'community')"
)


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


def _repair_legacy_source_authority_history() -> None:
    """Repair databases stamped 0045 before its authority-policy table was finalized.

    Current fresh 0045 databases already contain this table, so the IF NOT EXISTS
    path is a no-op there. This forward repair intentionally lives after 0045
    instead of rewriting persisted migration history.
    """

    op.execute(
        sa.text(
            f"""
            CREATE TABLE IF NOT EXISTS public.source_authority_policies (
                id UUID NOT NULL,
                policy_key VARCHAR(160) NOT NULL,
                canonical_domain VARCHAR(32) NOT NULL,
                source_class VARCHAR(32) NOT NULL,
                risk_class VARCHAR(24) NOT NULL,
                authority_state VARCHAR(16) NOT NULL,
                requires_exact_applicability BOOLEAN DEFAULT TRUE NOT NULL,
                minimum_evidence_count INTEGER DEFAULT 1 NOT NULL,
                rationale VARCHAR(500) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
                PRIMARY KEY (id),
                UNIQUE (policy_key),
                CONSTRAINT uq_source_authority_policies_scope
                    UNIQUE (canonical_domain, source_class, risk_class),
                CONSTRAINT ck_source_authority_policies_domain
                    CHECK (canonical_domain IN {DOMAIN_CHECK}),
                CONSTRAINT ck_source_authority_policies_source_class
                    CHECK (source_class IN {SOURCE_CLASS_CHECK}),
                CONSTRAINT ck_source_authority_policies_risk
                    CHECK (risk_class IN ('normal', 'safety_critical')),
                CONSTRAINT ck_source_authority_policies_state
                    CHECK (authority_state IN ('accepted', 'conditional', 'rejected')),
                CONSTRAINT ck_source_authority_policies_evidence_count
                    CHECK (minimum_evidence_count >= 1)
            )
            """
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_source_authority_policies_domain "
            "ON public.source_authority_policies (canonical_domain)"
        )
    )
    op.execute(
        sa.text(
            f"GRANT SELECT ON public.source_authority_policies TO {APP_ROLE}, {REVIEWER_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"REVOKE INSERT, UPDATE, DELETE ON public.source_authority_policies "
            f"FROM {APP_ROLE}, {REVIEWER_ROLE}"
        )
    )


def upgrade() -> None:
    _repair_legacy_source_authority_history()
    _ensure_role(CONTRIBUTOR_ROLE)
    _ensure_role(CURATOR_ROLE)

    op.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {CONTRIBUTOR_ROLE}"))
    op.execute(sa.text(f"GRANT USAGE ON SCHEMA {STAGING_SCHEMA} TO {CONTRIBUTOR_ROLE}"))
    op.execute(
        sa.text(
            f"GRANT SELECT ON public.catalog_sources, public.vehicle_configurations "
            f"TO {CONTRIBUTOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"GRANT INSERT ON {STAGING_SCHEMA}.ingestion_batches, "
            f"{STAGING_SCHEMA}.source_records TO {CONTRIBUTOR_ROLE}"
        )
    )

    # Candidate submitters never review evidence or write normalized/canonical truth.
    op.execute(
        sa.text(
            f"REVOKE SELECT, UPDATE, DELETE ON {STAGING_SCHEMA}.ingestion_batches, "
            f"{STAGING_SCHEMA}.source_records FROM {CONTRIBUTOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"REVOKE INSERT, UPDATE, DELETE ON public.catalog_verified_evidence, "
            f"public.mechanical_claims, public.canonical_record_versions, "
            f"public.canonical_record_evidence, public.canonical_conflicts, "
            f"public.canonical_conflict_items FROM {CONTRIBUTOR_ROLE}"
        )
    )

    op.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {CURATOR_ROLE}"))
    op.execute(
        sa.text(
            f"GRANT SELECT ON public.catalog_sources, public.catalog_verified_evidence, "
            f"public.vehicle_configurations, public.mechanical_claims, "
            f"public.source_authority_policies, public.canonical_conflicts, "
            f"public.canonical_conflict_items TO {CURATOR_ROLE}"
        )
    )
    op.execute(sa.text(f"GRANT INSERT ON public.mechanical_claims TO {CURATOR_ROLE}"))
    op.execute(
        sa.text(
            f"GRANT UPDATE (promotion_state, reviewed_at, reviewed_by) "
            f"ON public.mechanical_claims TO {CURATOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"GRANT INSERT ON public.canonical_conflicts, public.canonical_conflict_items "
            f"TO {CURATOR_ROLE}"
        )
    )

    # Phase 6A publication stops at normalized claims/conflicts. Domain tables remain read-only.
    canonical_domain_tables = (
        "vehicle_structure_nodes, component_definitions, part_identities, component_part_roles, "
        "part_fitments, part_relationships, physical_entities, physical_relationships, "
        "hardware_definitions, tool_equipment_definitions, workspace_definitions, "
        "material_definitions, vehicle_material_applicability, specification_definitions, "
        "vehicle_specification_values, repair_definitions, repair_operations, "
        "requirement_definitions, requirement_uses, procedure_actions, "
        "procedure_action_dependencies, diagnostic_signal_definitions, "
        "diagnostic_inspection_definitions, electrical_definitions"
    )
    op.execute(sa.text(f"GRANT SELECT ON {canonical_domain_tables} TO {CURATOR_ROLE}"))
    op.execute(
        sa.text(
            f"REVOKE INSERT, UPDATE, DELETE ON {canonical_domain_tables} FROM {CURATOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"REVOKE INSERT, UPDATE, DELETE ON public.catalog_sources, "
            f"public.catalog_verified_evidence, public.vehicle_configurations, "
            f"public.source_authority_policies, public.canonical_record_versions, "
            f"public.canonical_record_evidence FROM {CURATOR_ROLE}"
        )
    )


def downgrade() -> None:
    for role in (CURATOR_ROLE, CONTRIBUTOR_ROLE):
        op.execute(sa.text(f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {role}"))
        op.execute(
            sa.text(
                f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA {STAGING_SCHEMA} FROM {role}"
            )
        )
        op.execute(sa.text(f"REVOKE USAGE ON SCHEMA {STAGING_SCHEMA} FROM {role}"))
        op.execute(sa.text(f"REVOKE USAGE ON SCHEMA public FROM {role}"))
        op.execute(sa.text(f"REVOKE {role} FROM CURRENT_USER"))
        op.execute(sa.text(f"DROP ROLE IF EXISTS {role}"))
