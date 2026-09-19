"""Add canonical provenance, authority, versioning, and conflict representation."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0045_provenance_conflicts"
down_revision: str | None = "0044_capability_boundaries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "partgraph_app"
REVIEWER_ROLE = "partgraph_reviewer"
SHARED_TABLES = (
    "source_authority_policies, canonical_record_versions, canonical_record_evidence, "
    "canonical_conflicts, canonical_conflict_items"
)
DOMAIN_CHECK = (
    "('vehicle_identity', 'structure', 'part_identity', 'fitment', 'interchange', "
    "'physical_relationship', 'hardware', 'requirement', 'material', 'specification', "
    "'repair', 'procedure', 'downstream', 'diagnostic', 'electrical', 'capability')"
)
SOURCE_CLASS_CHECK = (
    "('government', 'oem_service', 'licensed_oem_derived', 'oem_parts', "
    "'industry_standard', 'retailer', 'community')"
)


def upgrade() -> None:
    op.create_table(
        "source_authority_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("policy_key", sa.String(length=160), nullable=False),
        sa.Column("canonical_domain", sa.String(length=32), nullable=False),
        sa.Column("source_class", sa.String(length=32), nullable=False),
        sa.Column("risk_class", sa.String(length=24), nullable=False),
        sa.Column("authority_state", sa.String(length=16), nullable=False),
        sa.Column(
            "requires_exact_applicability",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "minimum_evidence_count",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("rationale", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            f"canonical_domain IN {DOMAIN_CHECK}",
            name="ck_source_authority_policies_domain",
        ),
        sa.CheckConstraint(
            f"source_class IN {SOURCE_CLASS_CHECK}",
            name="ck_source_authority_policies_source_class",
        ),
        sa.CheckConstraint(
            "risk_class IN ('normal', 'safety_critical')",
            name="ck_source_authority_policies_risk",
        ),
        sa.CheckConstraint(
            "authority_state IN ('accepted', 'conditional', 'rejected')",
            name="ck_source_authority_policies_state",
        ),
        sa.CheckConstraint(
            "minimum_evidence_count >= 1",
            name="ck_source_authority_policies_evidence_count",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("policy_key"),
        sa.UniqueConstraint(
            "canonical_domain",
            "source_class",
            "risk_class",
            name="uq_source_authority_policies_scope",
        ),
    )
    op.create_index(
        "ix_source_authority_policies_domain",
        "source_authority_policies",
        ["canonical_domain"],
    )

    op.create_table(
        "canonical_record_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("canonical_domain", sa.String(length=32), nullable=False),
        sa.Column("record_type", sa.String(length=96), nullable=False),
        sa.Column("record_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("publication_state", sa.String(length=16), nullable=False),
        sa.Column("supersedes_version_id", sa.Uuid(), nullable=True),
        sa.Column("published_by", sa.String(length=128), nullable=False),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            f"canonical_domain IN {DOMAIN_CHECK}",
            name="ck_canonical_record_versions_domain",
        ),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_canonical_record_versions_version",
        ),
        sa.CheckConstraint(
            "publication_state IN ('verified', 'superseded', 'withdrawn')",
            name="ck_canonical_record_versions_state",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_version_id"],
            ["canonical_record_versions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "canonical_domain",
            "record_type",
            "record_id",
            "version",
            name="uq_canonical_record_versions_identity",
        ),
    )
    op.create_index(
        "ix_canonical_record_versions_domain",
        "canonical_record_versions",
        ["canonical_domain"],
    )
    op.create_index(
        "ix_canonical_record_versions_record",
        "canonical_record_versions",
        ["canonical_domain", "record_type", "record_id"],
    )

    op.create_table(
        "canonical_record_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("record_version_id", sa.Uuid(), nullable=False),
        sa.Column("verified_evidence_id", sa.Uuid(), nullable=False),
        sa.Column("mechanical_claim_id", sa.Uuid(), nullable=True),
        sa.Column(
            "evidence_role",
            sa.String(length=16),
            nullable=False,
            server_default="supports",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "evidence_role IN ('supports', 'excludes', 'conflicts')",
            name="ck_canonical_record_evidence_role",
        ),
        sa.ForeignKeyConstraint(
            ["record_version_id"],
            ["canonical_record_versions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["verified_evidence_id"],
            ["catalog_verified_evidence.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["mechanical_claim_id"],
            ["mechanical_claims.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "record_version_id",
            "verified_evidence_id",
            name="uq_canonical_record_evidence_pair",
        ),
    )
    op.create_index(
        "ix_canonical_record_evidence_version",
        "canonical_record_evidence",
        ["record_version_id"],
    )

    op.create_table(
        "canonical_conflicts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conflict_key", sa.String(length=160), nullable=False),
        sa.Column("canonical_domain", sa.String(length=32), nullable=False),
        sa.Column(
            "conflict_state",
            sa.String(length=16),
            nullable=False,
            server_default="open",
        ),
        sa.Column("resolution", sa.String(length=32), nullable=True),
        sa.Column("resolution_rationale", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=128), nullable=True),
        sa.CheckConstraint(
            f"canonical_domain IN {DOMAIN_CHECK}",
            name="ck_canonical_conflicts_domain",
        ),
        sa.CheckConstraint(
            "conflict_state IN ('open', 'resolved', 'blocked')",
            name="ck_canonical_conflicts_state",
        ),
        sa.CheckConstraint(
            "resolution IS NULL OR resolution IN ('accepted_evidence', 'superseded', "
            "'duplicate', 'insufficient_evidence', 'not_applicable')",
            name="ck_canonical_conflicts_resolution",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conflict_key"),
    )
    op.create_index(
        "ix_canonical_conflicts_domain_state",
        "canonical_conflicts",
        ["canonical_domain", "conflict_state"],
    )

    op.create_table(
        "canonical_conflict_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conflict_id", sa.Uuid(), nullable=False),
        sa.Column("mechanical_claim_id", sa.Uuid(), nullable=True),
        sa.Column("record_evidence_id", sa.Uuid(), nullable=True),
        sa.Column(
            "disposition",
            sa.String(length=16),
            nullable=False,
            server_default="contender",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "(mechanical_claim_id IS NOT NULL AND record_evidence_id IS NULL) OR "
            "(mechanical_claim_id IS NULL AND record_evidence_id IS NOT NULL)",
            name="ck_canonical_conflict_items_source",
        ),
        sa.CheckConstraint(
            "disposition IN ('contender', 'selected', 'rejected', 'superseded')",
            name="ck_canonical_conflict_items_disposition",
        ),
        sa.ForeignKeyConstraint(
            ["conflict_id"],
            ["canonical_conflicts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["mechanical_claim_id"],
            ["mechanical_claims.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["record_evidence_id"],
            ["canonical_record_evidence.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conflict_id",
            "mechanical_claim_id",
            name="uq_canonical_conflict_items_claim",
        ),
        sa.UniqueConstraint(
            "conflict_id",
            "record_evidence_id",
            name="uq_canonical_conflict_items_evidence",
        ),
    )
    op.create_index(
        "ix_canonical_conflict_items_conflict",
        "canonical_conflict_items",
        ["conflict_id"],
    )

    op.execute(sa.text(f"GRANT SELECT ON {SHARED_TABLES} TO {APP_ROLE}, {REVIEWER_ROLE}"))
    op.execute(
        sa.text(
            f"REVOKE INSERT, UPDATE, DELETE ON {SHARED_TABLES} FROM {APP_ROLE}, {REVIEWER_ROLE}"
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"REVOKE SELECT ON {SHARED_TABLES} FROM {APP_ROLE}, {REVIEWER_ROLE}"))
    op.drop_index(
        "ix_canonical_conflict_items_conflict",
        table_name="canonical_conflict_items",
    )
    op.drop_table("canonical_conflict_items")
    op.drop_index(
        "ix_canonical_conflicts_domain_state",
        table_name="canonical_conflicts",
    )
    op.drop_table("canonical_conflicts")
    op.drop_index(
        "ix_canonical_record_evidence_version",
        table_name="canonical_record_evidence",
    )
    op.drop_table("canonical_record_evidence")
    op.drop_index(
        "ix_canonical_record_versions_record",
        table_name="canonical_record_versions",
    )
    op.drop_index(
        "ix_canonical_record_versions_domain",
        table_name="canonical_record_versions",
    )
    op.drop_table("canonical_record_versions")
    op.drop_index(
        "ix_source_authority_policies_domain",
        table_name="source_authority_policies",
    )
    op.drop_table("source_authority_policies")
