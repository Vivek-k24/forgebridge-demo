"""Add persistent account roles for owner and operator authorization."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_auth_roles"
down_revision: str | None = "0020_catalog_coverage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ALLOWED_ROLES = "'owner', 'contributor', 'reviewer', 'curator', 'operator_admin'"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=32),
            nullable=False,
            server_default="owner",
        ),
    )
    op.create_check_constraint(
        "ck_users_role",
        "users",
        f"role IN ({_ALLOWED_ROLES})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")
