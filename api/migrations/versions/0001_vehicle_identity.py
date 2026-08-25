"""Create vehicle configuration identity records."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_vehicle_identity"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_table("vehicle_configurations")
