"""Add source-authority and materializer support for structure/specification claims."""

from collections.abc import Sequence
from uuid import UUID, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "0059_primary_vehicle_domains"
down_revision: str | None = "0058_downstream_materializer"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

POLICY_NAMESPACE = UUID("d25271d7-6df6-4f91-9427-f323ec8415f7")
MATERIALIZER_ROLE = "partgraph_materializer"
CURATOR_ROLE = "partgraph_curator"
NEW_CLAIM_DOMAINS = ("vehicle_structure", "vehicle_specification")
OLD_CLAIM_DOMAINS = (
    "vehicle_identity",
    "safety_campaign",
    "repair_requirement",
    "repair_procedure",
    "part_fitment",
)
ALL_CLAIM_DOMAINS = (*OLD_CLAIM_DOMAINS, *NEW_CLAIM_DOMAINS)
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
    "vehicle_structure": "structure",
    "vehicle_specification": "specification",
}
MATERIALIZATION_TABLES = (
    "vehicle_structure_nodes",
    "specification_definitions",
    "vehicle_specification_values",
)


def _claim_domain_sql(domains: tuple[str, ...]) -> str:
    return ", ".join(f"'{item}'" for item in domains)


def _authority(source_class: str, risk_class: str) -> tuple[str, str]:
    if source_class in {"oem_service", "licensed_oem_derived"}:
        if risk_class == "safety_critical":
            return (
                "conditional",
                "safety-critical structure/specification claims require explicit human review",
            )
        return (
            "accepted",
            "explicit exact-applicability OEM service evidence may establish vehicle structure and specifications",
        )
    return (
        "rejected",
        "this source class does not establish canonical exact-vehicle structure or service specifications",
    )


def _seed_policy_rows() -> None:
    table = sa.table(
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
    rows: list[dict[str, object]] = []
    for claim_domain in NEW_CLAIM_DOMAINS:
        for source_class in SOURCE_CLASSES:
            for risk_class in RISK_CLASSES:
                authority_state, rationale = _authority(source_class, risk_class)
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
    op.drop_constraint(
        "ck_mechanical_claims_domain",
        "mechanical_claims",
        type_="check",
    )
    op.create_check_constraint(
        "ck_mechanical_claims_domain",
        "mechanical_claims",
        f"claim_domain IN ({_claim_domain_sql(ALL_CLAIM_DOMAINS)})",
    )

    op.drop_constraint(
        "ck_source_authority_policies_claim_domain",
        "source_authority_policies",
        type_="check",
    )
    op.create_check_constraint(
        "ck_source_authority_policies_claim_domain",
        "source_authority_policies",
        "claim_domain IS NULL OR "
        f"claim_domain IN ({_claim_domain_sql(ALL_CLAIM_DOMAINS)})",
    )
    _seed_policy_rows()

    tables = ", ".join(f"public.{table}" for table in MATERIALIZATION_TABLES)
    op.execute(sa.text(f"GRANT SELECT, INSERT ON {tables} TO {MATERIALIZER_ROLE}"))
    op.execute(sa.text(f"REVOKE UPDATE, DELETE ON {tables} FROM {MATERIALIZER_ROLE}"))
    op.execute(sa.text(f"REVOKE INSERT, UPDATE, DELETE ON {tables} FROM {CURATOR_ROLE}"))


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM public.source_authority_policies "
            "WHERE claim_domain IN ('vehicle_structure', 'vehicle_specification')"
        )
    )

    tables = ", ".join(f"public.{table}" for table in MATERIALIZATION_TABLES)
    op.execute(sa.text(f"REVOKE INSERT ON {tables} FROM {MATERIALIZER_ROLE}"))
    op.execute(sa.text(f"REVOKE SELECT ON {tables} FROM {MATERIALIZER_ROLE}"))

    op.drop_constraint(
        "ck_source_authority_policies_claim_domain",
        "source_authority_policies",
        type_="check",
    )
    op.create_check_constraint(
        "ck_source_authority_policies_claim_domain",
        "source_authority_policies",
        "claim_domain IS NULL OR "
        f"claim_domain IN ({_claim_domain_sql(OLD_CLAIM_DOMAINS)})",
    )

    op.drop_constraint(
        "ck_mechanical_claims_domain",
        "mechanical_claims",
        type_="check",
    )
    op.create_check_constraint(
        "ck_mechanical_claims_domain",
        "mechanical_claims",
        f"claim_domain IN ({_claim_domain_sql(OLD_CLAIM_DOMAINS)})",
    )
