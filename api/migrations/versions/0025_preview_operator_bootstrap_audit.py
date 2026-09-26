"""Allow the isolated preview operator bootstrap audit action."""

from collections.abc import Sequence

from alembic import op

revision: str = "0025_preview_bootstrap"
down_revision: str | None = "0024_operator_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BASE_ACTIONS = (
    "'provider_created', 'provider_updated', 'provider_enabled', 'provider_disabled', "
    "'provider_credential_saved', 'provider_credential_removed'"
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_operator_audit_events_action",
        "operator_audit_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_operator_audit_events_action",
        "operator_audit_events",
        f"action IN ({_BASE_ACTIONS}, 'preview_operator_bootstrap')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_operator_audit_events_action",
        "operator_audit_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_operator_audit_events_action",
        "operator_audit_events",
        f"action IN ({_BASE_ACTIONS})",
    )
