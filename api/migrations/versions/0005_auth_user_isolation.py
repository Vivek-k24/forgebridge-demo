"""Add authentication storage and the first RLS-protected user-owned table."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_auth_user_isolation"
down_revision: str | None = "0004_catalog_staging_boundary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"


def upgrade() -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                    CREATE ROLE {APP_ROLE} NOLOGIN;
                END IF;
            END
            $$
            """
        )
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("username", sa.String(length=32), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "username ~ '^[a-z0-9_]+$' AND char_length(username) BETWEEN 3 AND 32",
            name="ck_users_username_format",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
    )
    op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"], unique=True)
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"], unique=False)

    op.create_table(
        "auth_rate_limits",
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.CheckConstraint("attempts >= 0", name="ck_auth_rate_limits_attempts"),
        sa.PrimaryKeyConstraint("action", "key_hash"),
    )

    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "units",
            sa.String(length=32),
            server_default="us_customary",
            nullable=False,
        ),
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
            "units IN ('us_customary', 'metric')",
            name="ck_user_preferences_units",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"))
    op.execute(
        sa.text(
            f"GRANT SELECT, INSERT, UPDATE ON users, auth_sessions, auth_rate_limits "
            f"TO {APP_ROLE}"
        )
    )
    op.execute(sa.text(f"GRANT DELETE ON auth_sessions, auth_rate_limits TO {APP_ROLE}"))
    op.execute(
        sa.text(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON user_preferences TO {APP_ROLE}"
        )
    )

    op.execute(sa.text("ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE user_preferences FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            CREATE POLICY user_preferences_owner
            ON user_preferences
            USING (
                user_id = NULLIF(current_setting('partgraph.user_id', true), '')::uuid
            )
            WITH CHECK (
                user_id = NULLIF(current_setting('partgraph.user_id', true), '')::uuid
            )
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP POLICY IF EXISTS user_preferences_owner ON user_preferences"))
    op.drop_table("user_preferences")
    op.drop_table("auth_rate_limits")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_token_hash", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
