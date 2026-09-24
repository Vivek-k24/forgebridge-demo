"""Grant the canonical materializer append-only part catalog creation authority."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0055_part_catalog"
down_revision: str | None = "0054_vehicle_verify_timestamp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CURATOR_ROLE = "partgraph_curator"
MATERIALIZER_ROLE = "partgraph_materializer"
PART_CATALOG_TABLES = (
    "component_definitions",
    "part_identities",
    "component_part_roles",
)


def upgrade() -> None:
    tables = ", ".join(f"public.{table}" for table in PART_CATALOG_TABLES)
    op.execute(sa.text(f"GRANT SELECT, INSERT ON {tables} TO {MATERIALIZER_ROLE}"))
    op.execute(sa.text(f"REVOKE UPDATE, DELETE ON {tables} FROM {MATERIALIZER_ROLE}"))
    op.execute(sa.text(f"REVOKE INSERT, UPDATE, DELETE ON {tables} FROM {CURATOR_ROLE}"))


def downgrade() -> None:
    tables = ", ".join(f"public.{table}" for table in PART_CATALOG_TABLES)
    op.execute(sa.text(f"REVOKE INSERT ON {tables} FROM {MATERIALIZER_ROLE}"))
    # SELECT on component_part_roles predates this migration and remains granted.
    op.execute(
        sa.text(
            "REVOKE SELECT ON public.component_definitions, public.part_identities "
            f"FROM {MATERIALIZER_ROLE}"
        )
    )
