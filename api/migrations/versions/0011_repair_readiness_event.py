"""Allow verified repair-readiness changes in repair-session event history."""

from collections.abc import Sequence

from alembic import op

revision: str = "0011_repair_readiness_event"
down_revision: str | None = "0010_manifest_readiness_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PREVIOUS_EVENT_TYPES = (
    "'session_started', 'session_paused', 'session_resumed', 'session_archived', "
    "'storage_location_created', 'fastener_recorded', 'fastener_state_changed', "
    "'inventory_item_recorded', 'inventory_state_changed', 'observation_recorded', "
    "'photo_evidence_added', 'photo_evidence_deleted'"
)


def _replace_event_type_constraint(event_types: str) -> None:
    op.drop_constraint(
        "ck_repair_session_events_type",
        "repair_session_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_repair_session_events_type",
        "repair_session_events",
        f"event_type IN ({event_types})",
    )


def upgrade() -> None:
    _replace_event_type_constraint(
        f"{_PREVIOUS_EVENT_TYPES}, 'readiness_state_changed'"
    )


def downgrade() -> None:
    _replace_event_type_constraint(_PREVIOUS_EVENT_TYPES)
