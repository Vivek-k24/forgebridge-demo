"""Move repair materialization writes behind a dedicated database role.

Revision 0048 reached a preview database before the privilege boundary was
refined. Keep 0048 immutable and correct both fresh and already-stamped 0048
histories here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0049_materializer_role"
down_revision: str | None = "0048_repair_materialization"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CURATOR_ROLE = "partgraph_curator"
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


def _ensure_materializer_role() -> None:
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
    _ensure_materializer_role()
    tables = ", ".join(f"public.{table}" for table in MATERIALIZATION_TABLES)

    # 0048 temporarily granted canonical writes directly to the curator role.
    # Remove those writes first so a failed later statement cannot leave both
    # roles authoritative.
    op.execute(sa.text(f"REVOKE INSERT ON {tables} FROM {CURATOR_ROLE}"))
    op.execute(
        sa.text(
            "REVOKE UPDATE (status, superseded_by_id) ON public.repair_definitions "
            f"FROM {CURATOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            "REVOKE UPDATE (publication_state) ON public.canonical_record_versions "
            f"FROM {CURATOR_ROLE}"
        )
    )

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
    op.execute(sa.text(f"REVOKE {MATERIALIZER_ROLE} FROM CURRENT_USER"))
    op.execute(sa.text(f"DROP ROLE IF EXISTS {MATERIALIZER_ROLE}"))

    # Restore the exact 0048 privilege state for a downgrade to that revision.
    op.execute(sa.text(f"GRANT INSERT ON {tables} TO {CURATOR_ROLE}"))
    op.execute(
        sa.text(
            "GRANT UPDATE (status, superseded_by_id) ON public.repair_definitions "
            f"TO {CURATOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            "GRANT UPDATE (publication_state) ON public.canonical_record_versions "
            f"TO {CURATOR_ROLE}"
        )
    )
