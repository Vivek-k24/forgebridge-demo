"""Add application-encrypted provider credentials with display-safe hints."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_provider_credentials"
down_revision: str | None = "0022_provider_registry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "provider_connections",
        sa.Column("credential_ciphertext", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "provider_connections",
        sa.Column("credential_nonce", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "provider_connections",
        sa.Column("credential_key_version", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "provider_connections",
        sa.Column("credential_fingerprint", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "provider_connections",
        sa.Column("credential_hint", sa.String(length=16), nullable=True),
    )
    op.create_check_constraint(
        "ck_provider_connections_encrypted_credential_complete",
        "provider_connections",
        "(credential_ciphertext IS NULL AND credential_nonce IS NULL "
        "AND credential_key_version IS NULL AND credential_fingerprint IS NULL "
        "AND credential_hint IS NULL) OR "
        "(credential_ciphertext IS NOT NULL AND credential_nonce IS NOT NULL "
        "AND credential_key_version IS NOT NULL AND credential_fingerprint IS NOT NULL "
        "AND credential_hint IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_provider_connections_credential_key_version",
        "provider_connections",
        "credential_key_version IS NULL OR credential_key_version >= 1",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_provider_connections_credential_key_version",
        "provider_connections",
        type_="check",
    )
    op.drop_constraint(
        "ck_provider_connections_encrypted_credential_complete",
        "provider_connections",
        type_="check",
    )
    op.drop_column("provider_connections", "credential_hint")
    op.drop_column("provider_connections", "credential_fingerprint")
    op.drop_column("provider_connections", "credential_key_version")
    op.drop_column("provider_connections", "credential_nonce")
    op.drop_column("provider_connections", "credential_ciphertext")
