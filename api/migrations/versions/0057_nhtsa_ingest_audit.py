"""Allow the audited operator action that stages a live NHTSA recall query."""

from collections.abc import Sequence

from alembic import op

revision: str = "0057_nhtsa_ingest_audit"
down_revision: str | None = "0056_reference_parts_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PREVIOUS_ACTIONS = (
    "provider_created",
    "provider_updated",
    "provider_enabled",
    "provider_disabled",
    "provider_credential_saved",
    "provider_credential_removed",
    "source_created",
    "source_updated",
    "provider_source_binding_created",
    "provider_source_binding_enabled",
    "provider_source_binding_disabled",
    "preview_operator_bootstrap",
    "user_role_changed",
    "reference_parts_dataset_staged",
)
_ACTIONS = _PREVIOUS_ACTIONS + ("nhtsa_recall_query_staged",)


def _action_check_sql(actions: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{value}'" for value in actions)
    return f"action IN ({quoted})"


def upgrade() -> None:
    op.drop_constraint(
        "ck_operator_audit_events_action",
        "operator_audit_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_operator_audit_events_action",
        "operator_audit_events",
        _action_check_sql(_ACTIONS),
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
        _action_check_sql(_PREVIOUS_ACTIONS),
    )
