"""Add capability policy and canonical verified procedure core."""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "0012_verified_procedure_core"
down_revision: str | None = "0011_repair_readiness_event"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _replace_claim_domain_constraint(include_procedure: bool) -> None:
    op.drop_constraint(
        "ck_mechanical_claims_domain",
        "mechanical_claims",
        type_="check",
    )
    domains = (
        "'vehicle_identity', 'safety_campaign', 'repair_requirement', "
        "'part_fitment'"
    )
    if include_procedure:
        domains = f"{domains}, 'repair_procedure'"
    op.create_check_constraint(
        "ck_mechanical_claims_domain",
        "mechanical_claims",
        f"claim_domain IN ({domains})",
    )


def upgrade() -> None:
    _replace_claim_domain_constraint(include_procedure=True)

    op.create_table(
        "repair_capability_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("policy_key", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("guidance_state", sa.String(length=32), nullable=False),
        sa.Column("rationale", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "guidance_state IN ('supported', 'professional_required', 'prohibited')",
            name="ck_repair_capability_policies_guidance_state",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "policy_key",
            name="uq_repair_capability_policies_policy_key",
        ),
    )

    policies = sa.table(
        "repair_capability_policies",
        sa.column("id", sa.Uuid()),
        sa.column("policy_key", sa.String()),
        sa.column("title", sa.String()),
        sa.column("guidance_state", sa.String()),
        sa.column("rationale", sa.String()),
    )
    op.bulk_insert(
        policies,
        [
            {
                "id": UUID("11111111-1111-4111-8111-111111111111"),
                "policy_key": "diy_supported",
                "title": "DIY guided workflow supported",
                "guidance_state": "supported",
                "rationale": (
                    "Verified guided repair actions may be shown when exact procedure "
                    "evidence and prerequisites are available."
                ),
            },
            {
                "id": UUID("22222222-2222-4222-8222-222222222222"),
                "policy_key": "professional_required",
                "title": "Professional service required",
                "guidance_state": "professional_required",
                "rationale": (
                    "PartGraph may provide non-procedural context, but step-by-step DIY "
                    "guidance is outside the supported capability boundary."
                ),
            },
            {
                "id": UUID("33333333-3333-4333-8333-333333333333"),
                "policy_key": "guided_prohibited",
                "title": "Guided workflow prohibited",
                "guidance_state": "prohibited",
                "rationale": (
                    "PartGraph must not provide a guided procedure for this repair "
                    "capability class."
                ),
            },
        ],
    )

    op.add_column(
        "repair_definitions",
        sa.Column("capability_policy_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_repair_definitions_capability_policy_id",
        "repair_definitions",
        "repair_capability_policies",
        ["capability_policy_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_repair_definitions_capability_policy_id",
        "repair_definitions",
        ["capability_policy_id"],
    )

    op.create_table(
        "procedure_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repair_definition_id", sa.Uuid(), nullable=False),
        sa.Column("action_key", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("warning_text", sa.Text(), nullable=True),
        sa.Column("workspace_note", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("position >= 0", name="ck_procedure_actions_position"),
        sa.ForeignKeyConstraint(
            ["repair_definition_id"],
            ["repair_definitions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repair_definition_id",
            "action_key",
            name="uq_procedure_actions_definition_key",
        ),
        sa.UniqueConstraint(
            "repair_definition_id",
            "position",
            name="uq_procedure_actions_definition_position",
        ),
    )
    op.create_index(
        "ix_procedure_actions_definition_position",
        "procedure_actions",
        ["repair_definition_id", "position"],
    )

    op.create_table(
        "procedure_action_dependencies",
        sa.Column("action_id", sa.Uuid(), nullable=False),
        sa.Column("prerequisite_action_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "action_id <> prerequisite_action_id",
            name="ck_procedure_action_dependencies_not_self",
        ),
        sa.ForeignKeyConstraint(
            ["action_id"], ["procedure_actions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["prerequisite_action_id"],
            ["procedure_actions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("action_id", "prerequisite_action_id"),
    )

    op.create_table(
        "procedure_action_requirement_uses",
        sa.Column("action_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_use_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["action_id"], ["procedure_actions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["requirement_use_id"], ["requirement_uses.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("action_id", "requirement_use_id"),
    )

    op.create_table(
        "procedure_action_evidence",
        sa.Column("action_id", sa.Uuid(), nullable=False),
        sa.Column("mechanical_claim_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["action_id"], ["procedure_actions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["mechanical_claim_id"], ["mechanical_claims.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("action_id", "mechanical_claim_id"),
    )


def downgrade() -> None:
    op.drop_table("procedure_action_evidence")
    op.drop_table("procedure_action_requirement_uses")
    op.drop_table("procedure_action_dependencies")
    op.drop_index(
        "ix_procedure_actions_definition_position",
        table_name="procedure_actions",
    )
    op.drop_table("procedure_actions")

    op.drop_index(
        "ix_repair_definitions_capability_policy_id",
        table_name="repair_definitions",
    )
    op.drop_constraint(
        "fk_repair_definitions_capability_policy_id",
        "repair_definitions",
        type_="foreignkey",
    )
    op.drop_column("repair_definitions", "capability_policy_id")
    op.drop_table("repair_capability_policies")

    _replace_claim_domain_constraint(include_procedure=False)
