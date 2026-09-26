"""Add a least-privilege database role for human evidence review."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030_reviewer_rbac"
down_revision: str | None = "0029_inventory_fluids"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVIEWER_ROLE = "partgraph_reviewer"
STAGING_SCHEMA = "catalog_staging"


def upgrade() -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{REVIEWER_ROLE}') THEN
                    CREATE ROLE {REVIEWER_ROLE} NOLOGIN;
                END IF;
            END
            $$
            """
        )
    )
    op.execute(sa.text(f"GRANT {REVIEWER_ROLE} TO CURRENT_USER WITH INHERIT FALSE, SET TRUE"))
    op.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {REVIEWER_ROLE}"))
    op.execute(sa.text(f"GRANT USAGE ON SCHEMA {STAGING_SCHEMA} TO {REVIEWER_ROLE}"))
    op.execute(
        sa.text(
            f"GRANT SELECT ON {STAGING_SCHEMA}.ingestion_batches, "
            f"{STAGING_SCHEMA}.source_records TO {REVIEWER_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"GRANT UPDATE (review_status, reviewed_at, reviewed_by) "
            f"ON {STAGING_SCHEMA}.source_records TO {REVIEWER_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"GRANT SELECT, INSERT ON public.catalog_verified_evidence TO {REVIEWER_ROLE}"
        )
    )

    # Reviewer authority deliberately stops at immutable verified evidence.
    # Canonical claims, repair definitions, applicability, and vehicle truth remain read-only.
    canonical_tables = (
        "catalog_sources, mechanical_claims, vehicle_configurations, "
        "repair_definitions, repair_operations, requirement_definitions, requirement_uses"
    )
    op.execute(sa.text(f"GRANT SELECT ON {canonical_tables} TO {REVIEWER_ROLE}"))
    op.execute(sa.text(f"REVOKE INSERT, UPDATE, DELETE ON {canonical_tables} FROM {REVIEWER_ROLE}"))


def downgrade() -> None:
    canonical_tables = (
        "catalog_sources, mechanical_claims, vehicle_configurations, "
        "repair_definitions, repair_operations, requirement_definitions, requirement_uses"
    )
    op.execute(sa.text(f"REVOKE SELECT ON {canonical_tables} FROM {REVIEWER_ROLE}"))
    op.execute(
        sa.text(
            f"REVOKE SELECT, INSERT ON public.catalog_verified_evidence FROM {REVIEWER_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"REVOKE UPDATE (review_status, reviewed_at, reviewed_by) "
            f"ON {STAGING_SCHEMA}.source_records FROM {REVIEWER_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"REVOKE SELECT ON {STAGING_SCHEMA}.ingestion_batches, "
            f"{STAGING_SCHEMA}.source_records FROM {REVIEWER_ROLE}"
        )
    )
    op.execute(sa.text(f"REVOKE USAGE ON SCHEMA {STAGING_SCHEMA} FROM {REVIEWER_ROLE}"))
    op.execute(sa.text(f"REVOKE USAGE ON SCHEMA public FROM {REVIEWER_ROLE}"))
    op.execute(sa.text(f"REVOKE {REVIEWER_ROLE} FROM CURRENT_USER"))
    op.execute(sa.text(f"DROP ROLE IF EXISTS {REVIEWER_ROLE}"))
