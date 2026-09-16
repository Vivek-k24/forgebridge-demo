"""Make repair-photo storage finalization durable across database commits."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0063_photo_storage_outbox"
down_revision: str | None = "0062_operator_rbac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MEDIA_WORKER_ROLE = "partgraph_media_worker"
PHOTO_TABLE = "public.repair_photo_evidence"


def upgrade() -> None:
    op.add_column(
        "repair_photo_evidence",
        sa.Column("storage_state", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "repair_photo_evidence",
        sa.Column("pending_content", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "repair_photo_evidence",
        sa.Column(
            "storage_attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "repair_photo_evidence",
        sa.Column("storage_error", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "repair_photo_evidence",
        sa.Column(
            "storage_updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.execute(
        sa.text(
            """
            UPDATE public.repair_photo_evidence
            SET storage_state = CASE
                WHEN deleted_at IS NULL THEN 'ready'
                ELSE 'deleted'
            END
            """
        )
    )
    op.alter_column("repair_photo_evidence", "storage_state", nullable=False)

    op.create_check_constraint(
        "ck_repair_photo_storage_state",
        "repair_photo_evidence",
        "storage_state IN ('pending_upload', 'ready', 'delete_pending', 'deleted')",
    )
    op.create_check_constraint(
        "ck_repair_photo_storage_attempts",
        "repair_photo_evidence",
        "storage_attempts >= 0",
    )
    op.create_check_constraint(
        "ck_repair_photo_storage_payload_state",
        "repair_photo_evidence",
        "((storage_state = 'pending_upload' AND deleted_at IS NULL AND pending_content IS NOT NULL) "
        "OR (storage_state = 'ready' AND deleted_at IS NULL AND pending_content IS NULL) "
        "OR (storage_state IN ('delete_pending', 'deleted') "
        "AND deleted_at IS NOT NULL AND pending_content IS NULL))",
    )
    op.create_index(
        "ix_repair_photo_storage_work",
        "repair_photo_evidence",
        ["storage_state", "storage_updated_at", "id"],
        postgresql_where=sa.text("storage_state IN ('pending_upload', 'delete_pending')"),
    )

    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{MEDIA_WORKER_ROLE}') THEN
                    CREATE ROLE {MEDIA_WORKER_ROLE} NOLOGIN;
                END IF;
            END
            $$
            """
        )
    )
    op.execute(
        sa.text(
            f"GRANT {MEDIA_WORKER_ROLE} TO CURRENT_USER WITH INHERIT FALSE, SET TRUE"
        )
    )
    op.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {MEDIA_WORKER_ROLE}"))
    op.execute(sa.text(f"GRANT SELECT ON {PHOTO_TABLE} TO {MEDIA_WORKER_ROLE}"))
    op.execute(
        sa.text(
            f"GRANT UPDATE (storage_state, pending_content, storage_attempts, storage_error, "
            f"storage_updated_at) ON {PHOTO_TABLE} TO {MEDIA_WORKER_ROLE}"
        )
    )
    op.execute(sa.text(f"REVOKE INSERT, DELETE ON {PHOTO_TABLE} FROM {MEDIA_WORKER_ROLE}"))

    # The table already has FORCE ROW LEVEL SECURITY. This dedicated policy lets only
    # the NOLOGIN media worker cross owner boundaries for storage finalization.
    op.execute(
        sa.text(
            f"""
            CREATE POLICY repair_photo_evidence_media_worker
            ON {PHOTO_TABLE}
            TO {MEDIA_WORKER_ROLE}
            USING (true)
            WITH CHECK (true)
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            f"DROP POLICY IF EXISTS repair_photo_evidence_media_worker ON {PHOTO_TABLE}"
        )
    )
    op.execute(sa.text(f"REVOKE ALL PRIVILEGES ON {PHOTO_TABLE} FROM {MEDIA_WORKER_ROLE}"))
    op.execute(sa.text(f"REVOKE USAGE ON SCHEMA public FROM {MEDIA_WORKER_ROLE}"))
    op.execute(sa.text(f"REVOKE {MEDIA_WORKER_ROLE} FROM CURRENT_USER"))
    op.execute(sa.text(f"DROP ROLE IF EXISTS {MEDIA_WORKER_ROLE}"))

    op.drop_index("ix_repair_photo_storage_work", table_name="repair_photo_evidence")
    op.drop_constraint(
        "ck_repair_photo_storage_payload_state",
        "repair_photo_evidence",
        type_="check",
    )
    op.drop_constraint(
        "ck_repair_photo_storage_attempts",
        "repair_photo_evidence",
        type_="check",
    )
    op.drop_constraint(
        "ck_repair_photo_storage_state",
        "repair_photo_evidence",
        type_="check",
    )
    op.drop_column("repair_photo_evidence", "storage_updated_at")
    op.drop_column("repair_photo_evidence", "storage_error")
    op.drop_column("repair_photo_evidence", "storage_attempts")
    op.drop_column("repair_photo_evidence", "pending_content")
    op.drop_column("repair_photo_evidence", "storage_state")
