"""Represent mechanical-claim source authority as canonical policy data."""

from collections.abc import Sequence
from uuid import UUID, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "0050_claim_authority_policy"
down_revision: str | None = "0049_materializer_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

POLICY_NAMESPACE = UUID("d25271d7-6df6-4f91-9427-f323ec8415f7")
CLAIM_DOMAINS = (
    "vehicle_identity",
    "safety_campaign",
    "repair_requirement",
    "repair_procedure",
    "part_fitment",
)
SOURCE_CLASSES = (
    "government",
    "oem_service",
    "licensed_oem_derived",
    "oem_parts",
    "industry_standard",
    "retailer",
    "community",
)
RISK_CLASSES = ("normal", "safety_critical")
CANONICAL_DOMAIN_BY_CLAIM = {
    "vehicle_identity": "vehicle_identity",
    "safety_campaign": None,
    "repair_requirement": "requirement",
    "repair_procedure": "procedure",
    "part_fitment": "fitment",
}


def _authority(source_class: str, claim_domain: str, risk_class: str) -> tuple[str, str]:
    if source_class == "government":
        if claim_domain == "vehicle_identity":
            return (
                "accepted",
                "government vehicle identity data is authoritative for identity evidence",
            )
        if claim_domain == "safety_campaign":
            return (
                "conditional",
                "campaign metadata is authoritative but repair implications require review",
            )
        return (
            "rejected",
            "government identity/safety datasets do not establish general repair requirements",
        )

    if source_class in {"oem_service", "licensed_oem_derived"}:
        if risk_class == "safety_critical":
            return (
                "conditional",
                "safety-critical mechanical claims require human review initially",
            )
        return (
            "accepted",
            "explicit exact-applicability OEM service evidence is eligible for promotion",
        )

    if source_class == "oem_parts":
        if claim_domain == "part_fitment":
            return (
                "accepted",
                "explicit exact-applicability OEM parts evidence may establish part fitment",
            )
        return (
            "rejected",
            "a parts catalog does not establish repair procedure or tool requirements",
        )

    if source_class == "industry_standard":
        return (
            "rejected",
            "industry standards normalize communication but do not supply application truth",
        )
    if source_class == "retailer":
        return (
            "rejected",
            "retailer listings are procurement evidence, not canonical mechanical truth",
        )
    return (
        "rejected",
        "community evidence may support discovery but cannot auto-promote mechanical truth",
    )


def _seed_rows(table: sa.Table) -> None:
    rows: list[dict[str, object]] = []
    for claim_domain in CLAIM_DOMAINS:
        for source_class in SOURCE_CLASSES:
            for risk_class in RISK_CLASSES:
                authority_state, rationale = _authority(
                    source_class,
                    claim_domain,
                    risk_class,
                )
                policy_key = f"claim.{claim_domain}.{source_class}.{risk_class}"
                rows.append(
                    {
                        "id": uuid5(POLICY_NAMESPACE, policy_key),
                        "policy_key": policy_key,
                        "canonical_domain": CANONICAL_DOMAIN_BY_CLAIM[claim_domain],
                        "claim_domain": claim_domain,
                        "source_class": source_class,
                        "risk_class": risk_class,
                        "authority_state": authority_state,
                        "requires_exact_applicability": True,
                        "minimum_evidence_count": 1,
                        "rationale": rationale,
                    }
                )
    op.bulk_insert(table, rows)


def upgrade() -> None:
    op.add_column(
        "source_authority_policies",
        sa.Column("claim_domain", sa.String(length=32), nullable=True),
    )
    op.alter_column(
        "source_authority_policies",
        "canonical_domain",
        existing_type=sa.String(length=32),
        nullable=True,
    )
    claim_domain_sql = ", ".join(f"'{item}'" for item in CLAIM_DOMAINS)
    op.create_check_constraint(
        "ck_source_authority_policies_claim_domain",
        "source_authority_policies",
        f"claim_domain IS NULL OR claim_domain IN ({claim_domain_sql})",
    )
    op.create_unique_constraint(
        "uq_source_authority_policies_claim_scope",
        "source_authority_policies",
        ["claim_domain", "source_class", "risk_class"],
    )
    op.create_index(
        "ix_source_authority_policies_claim_domain",
        "source_authority_policies",
        ["claim_domain"],
    )

    policy_table = sa.table(
        "source_authority_policies",
        sa.column("id", sa.Uuid()),
        sa.column("policy_key", sa.String()),
        sa.column("canonical_domain", sa.String()),
        sa.column("claim_domain", sa.String()),
        sa.column("source_class", sa.String()),
        sa.column("risk_class", sa.String()),
        sa.column("authority_state", sa.String()),
        sa.column("requires_exact_applicability", sa.Boolean()),
        sa.column("minimum_evidence_count", sa.Integer()),
        sa.column("rationale", sa.String()),
    )
    _seed_rows(policy_table)


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM public.source_authority_policies "
            "WHERE policy_key LIKE 'claim.%'"
        )
    )
    op.drop_index(
        "ix_source_authority_policies_claim_domain",
        table_name="source_authority_policies",
    )
    op.drop_constraint(
        "uq_source_authority_policies_claim_scope",
        "source_authority_policies",
        type_="unique",
    )
    op.drop_constraint(
        "ck_source_authority_policies_claim_domain",
        "source_authority_policies",
        type_="check",
    )
    op.alter_column(
        "source_authority_policies",
        "canonical_domain",
        existing_type=sa.String(length=32),
        nullable=False,
    )
    op.drop_column("source_authority_policies", "claim_domain")
