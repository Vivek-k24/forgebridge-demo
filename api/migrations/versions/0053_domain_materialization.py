"""Extend the canonical materializer to vehicle identity and exact part fitment."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0053_domain_materialization"
down_revision: str | None = "0052_operator_source_controls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CURATOR_ROLE = "partgraph_curator"
MATERIALIZER_ROLE = "partgraph_materializer"


def upgrade() -> None:
    # Canonical vehicle identity remains field-write protected. Materialization
    # may only advance the verification state after an explicit exact claim.
    op.execute(
        sa.text(
            "GRANT UPDATE (verification_status) ON public.vehicle_configurations "
            f"TO {MATERIALIZER_ROLE}"
        )
    )
    op.execute(
        sa.text(
            "GRANT SELECT ON public.component_part_roles, public.part_fitments, "
            f"public.source_authority_policies TO {MATERIALIZER_ROLE}"
        )
    )
    op.execute(sa.text(f"GRANT INSERT ON public.part_fitments TO {MATERIALIZER_ROLE}"))
    op.execute(sa.text(f"REVOKE UPDATE, DELETE ON public.part_fitments FROM {MATERIALIZER_ROLE}"))

    # Human curator authorization invokes the materializer role; the curator
    # role itself never receives direct writes to canonical domain tables.
    op.execute(sa.text(f"REVOKE INSERT, UPDATE, DELETE ON public.part_fitments FROM {CURATOR_ROLE}"))
    op.execute(
        sa.text(
            "REVOKE UPDATE (verification_status) ON public.vehicle_configurations "
            f"FROM {CURATOR_ROLE}"
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"REVOKE INSERT ON public.part_fitments FROM {MATERIALIZER_ROLE}"))
    op.execute(
        sa.text(
            "REVOKE SELECT ON public.component_part_roles, public.part_fitments, "
            f"public.source_authority_policies FROM {MATERIALIZER_ROLE}"
        )
    )
    op.execute(
        sa.text(
            "REVOKE UPDATE (verification_status) ON public.vehicle_configurations "
            f"FROM {MATERIALIZER_ROLE}"
        )
    )
