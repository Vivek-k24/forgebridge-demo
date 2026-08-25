from hashlib import sha256

import sqlalchemy as sa
from alembic import op

revision = "0002_vehicle_identity_resolution"
down_revision = "0001_vehicle_identity"
branch_labels = None
depends_on = None


def _canonical(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.casefold().split())


def _market(value: str | None) -> str:
    canonical = _canonical(value)
    aliases = {
        "u.s.": "us",
        "usa": "us",
        "united states": "us",
    }
    return aliases.get(canonical, canonical)


def _base_hash(year: int, market: str, make: str, model: str) -> str:
    parts = (str(year), _market(market), _canonical(make), _canonical(model))
    return sha256("\x1f".join(parts).encode()).hexdigest()


def upgrade() -> None:
    op.add_column(
        "vehicle_configurations",
        sa.Column("base_identity_hash", sa.String(length=64), nullable=True),
    )

    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, year, market, make, model FROM vehicle_configurations")
    ).mappings()
    for row in rows:
        connection.execute(
            sa.text(
                "UPDATE vehicle_configurations "
                "SET base_identity_hash = :base_identity_hash WHERE id = :id"
            ),
            {
                "base_identity_hash": _base_hash(
                    row["year"],
                    row["market"],
                    row["make"],
                    row["model"],
                ),
                "id": row["id"],
            },
        )

    op.alter_column("vehicle_configurations", "base_identity_hash", nullable=False)
    op.create_index(
        "ix_vehicle_configurations_base_identity_hash",
        "vehicle_configurations",
        ["base_identity_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_vehicle_configurations_base_identity_hash",
        table_name="vehicle_configurations",
    )
    op.drop_column("vehicle_configurations", "base_identity_hash")
