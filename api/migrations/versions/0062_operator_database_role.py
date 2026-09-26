"""Separate operator configuration writes from the general application role."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0062_operator_rbac"
down_revision: str | None = "0061_retire_legacy_specs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"
OPERATOR_ROLE = "partgraph_operator"

_OPERATOR_CONFIG_TABLES = (
    "public.provider_connections, "
    "public.provider_source_bindings, "
    "public.catalog_sources"
)


def upgrade() -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{OPERATOR_ROLE}') THEN
                    CREATE ROLE {OPERATOR_ROLE} NOLOGIN;
                END IF;
            END
            $$
            """
        )
    )
    op.execute(
        sa.text(
            f"GRANT {OPERATOR_ROLE} TO CURRENT_USER WITH INHERIT FALSE, SET TRUE"
        )
    )
    op.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {OPERATOR_ROLE}"))

    op.execute(
        sa.text(
            f"GRANT SELECT ON public.users, {_OPERATOR_CONFIG_TABLES}, "
            f"public.operator_audit_events TO {OPERATOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"GRANT INSERT, UPDATE ON {_OPERATOR_CONFIG_TABLES} TO {OPERATOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"GRANT SELECT, INSERT ON public.operator_audit_events TO {OPERATOR_ROLE}"
        )
    )
    op.execute(
        sa.text(f"GRANT UPDATE (role) ON public.users TO {OPERATOR_ROLE}")
    )

    # No operator route deletes registry/audit rows or mutates publication authority.
    op.execute(
        sa.text(
            f"REVOKE DELETE ON {_OPERATOR_CONFIG_TABLES}, public.operator_audit_events "
            f"FROM {OPERATOR_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"REVOKE INSERT, UPDATE, DELETE ON public.source_authority_policies "
            f"FROM {OPERATOR_ROLE}"
        )
    )

    # General authenticated requests retain read access but lose operator writes.
    op.execute(
        sa.text(
            f"REVOKE INSERT, UPDATE, DELETE ON {_OPERATOR_CONFIG_TABLES} FROM {APP_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f"REVOKE INSERT, UPDATE, DELETE ON public.operator_audit_events FROM {APP_ROLE}"
        )
    )

    # Authentication still needs password rehashes, but only operators may change roles.
    op.execute(sa.text(f"REVOKE UPDATE ON public.users FROM {APP_ROLE}"))
    op.execute(
        sa.text(f"GRANT UPDATE (password_hash) ON public.users TO {APP_ROLE}")
    )


def downgrade() -> None:
    op.execute(
        sa.text(f"REVOKE UPDATE (password_hash) ON public.users FROM {APP_ROLE}")
    )
    op.execute(sa.text(f"GRANT UPDATE ON public.users TO {APP_ROLE}"))
    op.execute(
        sa.text(
            f"GRANT INSERT, UPDATE ON {_OPERATOR_CONFIG_TABLES} TO {APP_ROLE}"
        )
    )
    op.execute(
        sa.text(f"GRANT INSERT ON public.operator_audit_events TO {APP_ROLE}")
    )

    op.execute(
        sa.text(
            f"REVOKE ALL PRIVILEGES ON public.users, {_OPERATOR_CONFIG_TABLES}, "
            f"public.operator_audit_events, public.source_authority_policies "
            f"FROM {OPERATOR_ROLE}"
        )
    )
    op.execute(sa.text(f"REVOKE USAGE ON SCHEMA public FROM {OPERATOR_ROLE}"))
    op.execute(sa.text(f"REVOKE {OPERATOR_ROLE} FROM CURRENT_USER"))
    op.execute(sa.text(f"DROP ROLE IF EXISTS {OPERATOR_ROLE}"))
