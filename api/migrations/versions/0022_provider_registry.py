"""Add operator-managed provider registry without storing API secret values."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022_provider_registry"
down_revision: str | None = "0021_auth_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"


def upgrade() -> None:
    op.create_table(
        "provider_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_key", sa.String(length=96), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("provider_kind", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.String(length=1024), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "capabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("secret_ref", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "provider_kind IN ('internal_data', 'vehicle_data', 'ai', 'manufacturer')",
            name="ck_provider_connections_kind",
        ),
        sa.CheckConstraint(
            "provider_key ~ '^[a-z0-9][a-z0-9_-]{1,95}$'",
            name="ck_provider_connections_key_format",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_key", name="uq_provider_connections_key"),
    )
    op.create_index(
        "ix_provider_connections_provider_key",
        "provider_connections",
        ["provider_key"],
        unique=True,
    )

    op.execute(sa.text("REVOKE ALL ON provider_connections FROM PUBLIC"))
    op.execute(
        sa.text(
            f"GRANT SELECT, INSERT, UPDATE ON provider_connections TO {APP_ROLE}"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_provider_connections_provider_key", table_name="provider_connections")
    op.drop_table("provider_connections")
