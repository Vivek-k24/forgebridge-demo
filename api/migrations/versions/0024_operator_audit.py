"""Add append-only administrator audit events."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024_operator_audit"
down_revision: str | None = "0023_provider_credentials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"


def upgrade() -> None:
    op.create_table(
        "operator_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column(
            "event_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('provider_created', 'provider_updated', 'provider_enabled', "
            "'provider_disabled', 'provider_credential_saved', 'provider_credential_removed')",
            name="ck_operator_audit_events_action",
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operator_audit_events_actor_user_id",
        "operator_audit_events",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_operator_audit_events_action",
        "operator_audit_events",
        ["action"],
        unique=False,
    )
    op.create_index(
        "ix_operator_audit_events_target_id",
        "operator_audit_events",
        ["target_id"],
        unique=False,
    )
    op.create_index(
        "ix_operator_audit_events_created_at",
        "operator_audit_events",
        ["created_at"],
        unique=False,
    )
    op.execute(
        sa.text(
            f"GRANT SELECT, INSERT ON operator_audit_events TO {APP_ROLE}"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_operator_audit_events_created_at", table_name="operator_audit_events")
    op.drop_index("ix_operator_audit_events_target_id", table_name="operator_audit_events")
    op.drop_index("ix_operator_audit_events_action", table_name="operator_audit_events")
    op.drop_index("ix_operator_audit_events_actor_user_id", table_name="operator_audit_events")
    op.drop_table("operator_audit_events")
