"""Compatibility bridge for the retired Block 2 identity-resolution revision.

Some developer databases were created while the short-lived
`0002_vehicle_identity_resolution` migration existed. The canonical identity
replacement intentionally resets the Block 2 vehicle table, so no legacy
schema transformation is required here. Keeping this no-op revision in the
linear history lets those persisted databases advance safely without deleting
their PostgreSQL volume.
"""

from collections.abc import Sequence

revision: str = "0002_vehicle_identity_resolution"
down_revision: str | None = "0001_vehicle_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Preserve the retired revision as a migration-history compatibility point."""


def downgrade() -> None:
    """The compatibility revision never changed schema state."""
