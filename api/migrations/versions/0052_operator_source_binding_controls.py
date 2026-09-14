"""Allow audited operator management of sources and provider/source bindings."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0052_operator_source_binding_controls"
down_revision: str | None = "0051_provider_source_binding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"

_ACTIONS = (
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
)


def _action_check_sql() -> str:
    quoted = ", ".join(f"'{value}'" for value in _ACTIONS)
    return f"action IN ({quoted})"


def upgrade() -> None:
    # The application role can mutate source registry metadata only through the
    # authenticated operator API. Authority-policy rows remain read-only.
    op.execute(sa.text(f"GRANT INSERT, UPDATE ON public.catalog_sources TO {APP_ROLE}"))
    op.execute(sa.text(f"REVOKE DELETE ON public.catalog_sources FROM {APP_ROLE}"))
    op.execute(sa.text(f"REVOKE INSERT, UPDATE, DELETE ON public.source_authority_policies FROM {APP_ROLE}"))

    op.drop_constraint(
        "ck_operator_audit_events_action",
        "operator_audit_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_operator_audit_events_action",
        "operator_audit_events",
        _action_check_sql(),
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_operator_audit_events_action",
        "operator_audit_events",
        type_="check",
    )
    legacy_actions = _ACTIONS[:6] + _ACTIONS[-2:]
    quoted = ", ".join(f"'{value}'" for value in legacy_actions)
    op.create_check_constraint(
        "ck_operator_audit_events_action",
        "operator_audit_events",
        f"action IN ({quoted})",
    )
    op.execute(sa.text(f"REVOKE INSERT, UPDATE ON public.catalog_sources FROM {APP_ROLE}"))
