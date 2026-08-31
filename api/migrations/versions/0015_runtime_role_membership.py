"""Allow the deployment database login to assume the restricted app role."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_runtime_role_membership"
down_revision: str | None = "0014_ai_invocation_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"


def upgrade() -> None:
    op.execute(
        sa.text(
            f"GRANT {APP_ROLE} TO CURRENT_USER WITH INHERIT FALSE, SET TRUE"
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"REVOKE {APP_ROLE} FROM CURRENT_USER"))
