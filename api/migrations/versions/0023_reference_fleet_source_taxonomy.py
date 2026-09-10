"""Add public-source classes needed by the curated reference fleet."""

from collections.abc import Sequence

from alembic import op

revision: str = "0023_reference_fleet_sources"
down_revision: str | None = "0022_identity_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BASE_SOURCE_CLASSES = (
    "government",
    "oem_service",
    "licensed_oem_derived",
    "oem_parts",
    "industry_standard",
    "retailer",
    "community",
)
REFERENCE_FLEET_SOURCE_CLASSES = (
    "manufacturer",
    "vehicle_reference",
)


def _replace_source_class_constraint(*, include_reference_classes: bool) -> None:
    op.drop_constraint("ck_catalog_sources_class", "catalog_sources", type_="check")
    values = list(BASE_SOURCE_CLASSES)
    if include_reference_classes:
        values.extend(REFERENCE_FLEET_SOURCE_CLASSES)
    quoted = ", ".join(f"'{value}'" for value in values)
    op.create_check_constraint(
        "ck_catalog_sources_class",
        "catalog_sources",
        f"source_class IN ({quoted})",
    )


def upgrade() -> None:
    _replace_source_class_constraint(include_reference_classes=True)


def downgrade() -> None:
    _replace_source_class_constraint(include_reference_classes=False)
