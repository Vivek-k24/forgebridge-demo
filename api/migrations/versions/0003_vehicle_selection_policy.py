"""Align canonical vehicle storage with the supported selection policy."""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_vehicle_selection_policy"
down_revision: str | None = "0002_canonical_vehicle_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_vehicle_configurations_year",
        "vehicle_configurations",
        type_="check",
    )
    op.create_check_constraint(
        "ck_vehicle_configurations_year",
        "vehicle_configurations",
        "year >= 1996 AND year <= 2100",
    )
    op.create_index(
        "ix_vehicle_configurations_selection",
        "vehicle_configurations",
        ["market", "year", "make", "model", "trim"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_vehicle_configurations_selection",
        table_name="vehicle_configurations",
    )
    op.drop_constraint(
        "ck_vehicle_configurations_year",
        "vehicle_configurations",
        type_="check",
    )
    op.create_check_constraint(
        "ck_vehicle_configurations_year",
        "vehicle_configurations",
        "year >= 1886 AND year <= 2100",
    )
