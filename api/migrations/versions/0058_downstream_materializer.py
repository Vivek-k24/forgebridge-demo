"""Allow the canonical materializer to append downstream repair relationships."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0058_downstream_materializer"
down_revision: str | None = "0057_nhtsa_ingest_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"
CURATOR_ROLE = "partgraph_curator"
MATERIALIZER_ROLE = "partgraph_materializer"
DOWNSTREAM_TABLES = (
    "procedure_action_milestones",
    "repair_downstream_requirements",
    "repair_downstream_requirement_evidence",
)


def upgrade() -> None:
    tables = ", ".join(f"public.{table}" for table in DOWNSTREAM_TABLES)
    op.execute(sa.text(f"GRANT SELECT, INSERT ON {tables} TO {MATERIALIZER_ROLE}"))
    op.execute(sa.text(f"REVOKE UPDATE, DELETE ON {tables} FROM {MATERIALIZER_ROLE}"))
    op.execute(sa.text(f"REVOKE INSERT, UPDATE, DELETE ON {tables} FROM {CURATOR_ROLE}"))
    op.execute(sa.text(f"REVOKE INSERT, UPDATE, DELETE ON {tables} FROM {APP_ROLE}"))


def downgrade() -> None:
    tables = ", ".join(f"public.{table}" for table in DOWNSTREAM_TABLES)
    op.execute(sa.text(f"REVOKE INSERT ON {tables} FROM {MATERIALIZER_ROLE}"))
    op.execute(sa.text(f"REVOKE SELECT ON {tables} FROM {MATERIALIZER_ROLE}"))
