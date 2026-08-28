"""Add private UserVehicle storage and user-scoped VIN decode cache."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_user_vehicle_vin"
down_revision: str | None = "0005_auth_user_isolation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"


def _owner_policy(table: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY {table}_owner
            ON {table}
            USING (
                user_id = NULLIF(current_setting('partgraph.user_id', true), '')::uuid
            )
            WITH CHECK (
                user_id = NULLIF(current_setting('partgraph.user_id', true), '')::uuid
            )
            """
        )
    )


def upgrade() -> None:
    op.create_table(
        "user_vehicles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_configuration_id", sa.Uuid(), nullable=True),
        sa.Column("nickname", sa.String(length=80), nullable=True),
        sa.Column("identity_source", sa.String(length=16), nullable=False),
        sa.Column("identity_resolution", sa.String(length=32), nullable=False),
        sa.Column("identity_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("vin_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("vin_nonce", sa.LargeBinary(), nullable=True),
        sa.Column("vin_key_version", sa.SmallInteger(), nullable=True),
        sa.Column("vin_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("vin_last6", sa.String(length=6), nullable=True),
        sa.Column("decoder_provider", sa.String(length=32), nullable=True),
        sa.Column("decoder_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
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
            "identity_source IN ('manual', 'vin')",
            name="ck_user_vehicles_identity_source",
        ),
        sa.CheckConstraint(
            "identity_resolution IN ('matched', 'ambiguous', 'manual_candidate')",
            name="ck_user_vehicles_identity_resolution",
        ),
        sa.CheckConstraint(
            "(vin_ciphertext IS NULL AND vin_nonce IS NULL AND vin_key_version IS NULL "
            "AND vin_fingerprint IS NULL AND vin_last6 IS NULL) OR "
            "(vin_ciphertext IS NOT NULL AND vin_nonce IS NOT NULL "
            "AND vin_key_version IS NOT NULL AND vin_fingerprint IS NOT NULL "
            "AND vin_last6 IS NOT NULL)",
            name="ck_user_vehicles_vin_all_or_none",
        ),
        sa.CheckConstraint(
            "vin_last6 IS NULL OR vin_last6 ~ '^[A-HJ-NPR-Z0-9]{6}$'",
            name="ck_user_vehicles_vin_last6",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["canonical_configuration_id"],
            ["vehicle_configurations.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "vin_fingerprint",
            name="uq_user_vehicles_owner_vin",
        ),
    )
    op.create_index("ix_user_vehicles_user_id", "user_vehicles", ["user_id"])
    op.create_index(
        "ix_user_vehicles_owner_active",
        "user_vehicles",
        ["user_id", "archived_at"],
    )

    op.create_table(
        "vin_decode_cache",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("vin_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("market", sa.String(length=2), nullable=False),
        sa.Column("identity_resolution", sa.String(length=32), nullable=False),
        sa.Column("identity_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("canonical_match_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.CheckConstraint("market IN ('US', 'CA')", name="ck_vin_decode_cache_market"),
        sa.CheckConstraint(
            "identity_resolution IN ('matched', 'ambiguous', 'manual_candidate')",
            name="ck_vin_decode_cache_resolution",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "vin_fingerprint",
            "market",
            name="uq_vin_decode_cache_owner_vin_market",
        ),
    )
    op.create_index("ix_vin_decode_cache_user_id", "vin_decode_cache", ["user_id"])
    op.create_index(
        "ix_vin_decode_cache_expiry",
        "vin_decode_cache",
        ["user_id", "expires_at"],
    )

    op.execute(sa.text(f"GRANT SELECT ON vehicle_configurations TO {APP_ROLE}"))
    op.execute(
        sa.text(
            f"GRANT SELECT, INSERT, UPDATE ON user_vehicles, vin_decode_cache TO {APP_ROLE}"
        )
    )
    _owner_policy("user_vehicles")
    _owner_policy("vin_decode_cache")


def downgrade() -> None:
    op.execute(sa.text("DROP POLICY IF EXISTS vin_decode_cache_owner ON vin_decode_cache"))
    op.execute(sa.text("DROP POLICY IF EXISTS user_vehicles_owner ON user_vehicles"))
    op.drop_index("ix_vin_decode_cache_expiry", table_name="vin_decode_cache")
    op.drop_index("ix_vin_decode_cache_user_id", table_name="vin_decode_cache")
    op.drop_table("vin_decode_cache")
    op.drop_index("ix_user_vehicles_owner_active", table_name="user_vehicles")
    op.drop_index("ix_user_vehicles_user_id", table_name="user_vehicles")
    op.drop_table("user_vehicles")
    op.execute(sa.text(f"REVOKE SELECT ON vehicle_configurations FROM {APP_ROLE}"))
