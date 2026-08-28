"""Replace Block 2 test identities with canonical vehicle identity storage."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_canonical_vehicle_identity"
down_revision: str | None = "0002_vehicle_identity_resolution"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_canonical_table() -> None:
    op.create_table(
        "vehicle_configurations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("identity_hash", sa.String(length=64), nullable=False),
        sa.Column("base_identity_hash", sa.String(length=64), nullable=False),
        sa.Column("canonicalization_version", sa.SmallInteger(), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("market", sa.String(length=32), nullable=False),
        sa.Column("make", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=96), nullable=False),
        sa.Column("generation", sa.String(length=96), nullable=True),
        sa.Column("trim", sa.String(length=128), nullable=True),
        sa.Column("body_style", sa.String(length=64), nullable=True),
        sa.Column("engine", sa.String(length=128), nullable=True),
        sa.Column("transmission", sa.String(length=128), nullable=True),
        sa.Column("drivetrain", sa.String(length=64), nullable=True),
        sa.Column("identity_source", sa.String(length=32), nullable=False),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "year >= 1886 AND year <= 2100",
            name="ck_vehicle_configurations_year",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "identity_hash",
            name="uq_vehicle_configurations_identity_hash",
        ),
    )
    op.create_index(
        "ix_vehicle_configurations_base_identity_hash",
        "vehicle_configurations",
        ["base_identity_hash"],
        unique=False,
    )


def _create_block2_table() -> None:
    op.create_table(
        "vehicle_configurations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("identity_hash", sa.String(length=64), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("market", sa.String(length=32), nullable=False),
        sa.Column("make", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=96), nullable=False),
        sa.Column("generation", sa.String(length=96), nullable=True),
        sa.Column("trim", sa.String(length=128), nullable=True),
        sa.Column("body_style", sa.String(length=64), nullable=True),
        sa.Column("engine", sa.String(length=128), nullable=True),
        sa.Column("transmission", sa.String(length=128), nullable=True),
        sa.Column("drivetrain", sa.String(length=64), nullable=True),
        sa.Column("identity_source", sa.String(length=32), nullable=False),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "year >= 1886 AND year <= 2100",
            name="ck_vehicle_configurations_year",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "identity_hash",
            name="uq_vehicle_configurations_identity_hash",
        ),
    )


def upgrade() -> None:
    # Block 2 contained manual test identities only. Resetting here prevents the
    # incorrect tuple-based duplicates from becoming permanent canonical data.
    op.drop_table("vehicle_configurations")
    _create_canonical_table()


def downgrade() -> None:
    op.drop_index(
        "ix_vehicle_configurations_base_identity_hash",
        table_name="vehicle_configurations",
    )
    op.drop_table("vehicle_configurations")
    _create_block2_table()
