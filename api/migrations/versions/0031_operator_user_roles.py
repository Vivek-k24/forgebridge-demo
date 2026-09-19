"""Allow append-only audit records for operator-managed user role changes."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031_operator_user_roles"
down_revision: str | None = "0030_reviewer_rbac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT = "ck_operator_audit_events_action"
_OLD_ACTIONS = (
    "'provider_created', 'provider_updated', 'provider_enabled', 'provider_disabled', "
    "'provider_credential_saved', 'provider_credential_removed', 'preview_operator_bootstrap'"
)
_NEW_ACTIONS = _OLD_ACTIONS + ", 'user_role_changed'"


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "operator_audit_events", type_="check")
    op.create_check_constraint(
        _CONSTRAINT,
        "operator_audit_events",
        f"action IN ({_NEW_ACTIONS})",
    )


def downgrade() -> None:
    # Preserve immutable audit history. NOT VALID permits historical role-change
    # records while restoring the old constraint for future writes.
    op.drop_constraint(_CONSTRAINT, "operator_audit_events", type_="check")
    op.execute(
        sa.text(
            f"ALTER TABLE operator_audit_events ADD CONSTRAINT {_CONSTRAINT} "
            f"CHECK (action IN ({_OLD_ACTIONS})) NOT VALID"
        )
    )
