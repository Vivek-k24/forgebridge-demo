"""Complete least-privilege read grants for shared canonical and review data."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032_shared_read_privileges"
down_revision: str | None = "0031_operator_user_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"
REVIEWER_ROLE = "partgraph_reviewer"


def upgrade() -> None:
    # Ordinary authenticated users may read the verified shared vehicle profile.
    op.execute(
        sa.text(
            f"GRANT SELECT ON public.vehicle_specification_profiles TO {APP_ROLE}"
        )
    )

    # Coverage is an internal review surface. Keep it out of the ordinary app role
    # and expose it only after the API narrows the transaction to reviewer authority.
    coverage_tables = "public.catalog_coverage_batches, public.catalog_coverage_items"
    op.execute(sa.text(f"GRANT SELECT ON {coverage_tables} TO {REVIEWER_ROLE}"))
    op.execute(
        sa.text(
            f"REVOKE INSERT, UPDATE, DELETE ON {coverage_tables} FROM {REVIEWER_ROLE}"
        )
    )


def downgrade() -> None:
    coverage_tables = "public.catalog_coverage_batches, public.catalog_coverage_items"
    op.execute(sa.text(f"REVOKE SELECT ON {coverage_tables} FROM {REVIEWER_ROLE}"))
    op.execute(
        sa.text(
            f"REVOKE SELECT ON public.vehicle_specification_profiles FROM {APP_ROLE}"
        )
    )
