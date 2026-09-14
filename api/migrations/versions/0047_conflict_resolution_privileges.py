"""Allow curators to resolve claim conflicts without broader canonical writes."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0047_conflict_resolution"
down_revision: str | None = "0046_pipeline_actor_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CURATOR_ROLE = "partgraph_curator"


def upgrade() -> None:
    op.execute(
        sa.text(
            f"GRANT UPDATE (superseded_by_id) ON public.mechanical_claims TO {CURATOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            "GRANT UPDATE (conflict_state, resolution, resolution_rationale, resolved_at, resolved_by) "
            f"ON public.canonical_conflicts TO {CURATOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"GRANT UPDATE (disposition) ON public.canonical_conflict_items TO {CURATOR_ROLE}"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            f"REVOKE UPDATE (disposition) ON public.canonical_conflict_items FROM {CURATOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            "REVOKE UPDATE (conflict_state, resolution, resolution_rationale, resolved_at, resolved_by) "
            f"ON public.canonical_conflicts FROM {CURATOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"REVOKE UPDATE (superseded_by_id) ON public.mechanical_claims FROM {CURATOR_ROLE}"
        )
    )
