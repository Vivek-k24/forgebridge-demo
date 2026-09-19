"""Allow the materializer to timestamp verified vehicle identity changes."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0054_vehicle_verify_timestamp"
down_revision: str | None = "0053_domain_materialization"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CURATOR_ROLE = "partgraph_curator"
MATERIALIZER_ROLE = "partgraph_materializer"


def upgrade() -> None:
    # VehicleConfiguration.updated_at has an ORM on-update expression, so a
    # legitimate verification-status transition updates this audit timestamp
    # in the same statement. Keep the grant column-scoped.
    op.execute(
        sa.text(
            "GRANT UPDATE (updated_at) ON public.vehicle_configurations "
            f"TO {MATERIALIZER_ROLE}"
        )
    )
    op.execute(
        sa.text(
            "REVOKE UPDATE (updated_at) ON public.vehicle_configurations "
            f"FROM {CURATOR_ROLE}"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "REVOKE UPDATE (updated_at) ON public.vehicle_configurations "
            f"FROM {MATERIALIZER_ROLE}"
        )
    )
