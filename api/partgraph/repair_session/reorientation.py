from __future__ import annotations

from collections import Counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..repair_memory.models import (
    RepairFastener,
    RepairInventoryItem,
    RepairObservation,
    RepairPhotoEvidence,
    RepairStorageLocation,
)
from .models import RepairSessionEvent
from .schemas import (
    RepairSessionReorientationRead,
    ResumeActivityRead,
    ResumeAttentionItemRead,
    ResumeCountsRead,
    ResumeEvidenceRead,
    ResumeNextVerifiedActionRead,
    ResumeObservationRead,
    ResumeStorageGroupRead,
)

DOMAIN_EVENT_TYPES = {
    "storage_location_created",
    "fastener_recorded",
    "fastener_state_changed",
    "inventory_item_recorded",
    "inventory_state_changed",
    "observation_recorded",
    "photo_evidence_added",
    "photo_evidence_deleted",
}


def _payload_uuid(event: RepairSessionEvent, key: str) -> UUID | None:
    value = event.payload.get(key)
    if value is None:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _activity_label(
    event: RepairSessionEvent,
    *,
    fasteners: dict[UUID, RepairFastener],
    inventory: dict[UUID, RepairInventoryItem],
    locations: dict[UUID, RepairStorageLocation],
    observations: dict[UUID, RepairObservation],
) -> str:
    if event.event_type == "session_started":
        return "Repair started"
    if event.event_type == "session_paused":
        return "Repair paused"
    if event.event_type == "session_resumed":
        return "Repair resumed"
    if event.event_type == "session_archived":
        return "Repair archived"
    if event.event_type == "storage_location_created":
        row = locations.get(_payload_uuid(event, "storage_location_id"))
        return f"Storage location recorded · {row.label}" if row else "Storage location recorded"
    if event.event_type in {"fastener_recorded", "fastener_state_changed"}:
        row = fasteners.get(_payload_uuid(event, "fastener_id"))
        if row is None:
            return "Hardware state recorded"
        state = row.physical_state.replace("_", " ")
        return f"{row.label} · {state}"
    if event.event_type in {"inventory_item_recorded", "inventory_state_changed"}:
        row = inventory.get(_payload_uuid(event, "inventory_item_id"))
        if row is None:
            return "Parts readiness updated"
        state = row.procurement_state.replace("_", " ")
        return f"{row.name} · {state}"
    if event.event_type == "observation_recorded":
        row = observations.get(_payload_uuid(event, "observation_id"))
        return f"Observation · {row.text}" if row else "Observation recorded"
    if event.event_type == "photo_evidence_added":
        purpose = str(event.payload.get("purpose") or "general").replace("_", " ")
        return f"Photo added · {purpose}"
    if event.event_type == "photo_evidence_deleted":
        return "Photo evidence deleted"
    return "Repair state updated"


def _activity(
    event: RepairSessionEvent,
    *,
    fasteners: dict[UUID, RepairFastener],
    inventory: dict[UUID, RepairInventoryItem],
    locations: dict[UUID, RepairStorageLocation],
    observations: dict[UUID, RepairObservation],
) -> ResumeActivityRead:
    return ResumeActivityRead(
        sequence=event.sequence,
        event_type=event.event_type,
        label=_activity_label(
            event,
            fasteners=fasteners,
            inventory=inventory,
            locations=locations,
            observations=observations,
        ),
        created_at=event.created_at,
    )


async def build_reorientation(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    last_event: RepairSessionEvent,
) -> RepairSessionReorientationRead:
    fastener_rows = list(
        await session.scalars(
            select(RepairFastener)
            .where(RepairFastener.user_id == user_id, RepairFastener.session_id == session_id)
            .order_by(RepairFastener.created_at, RepairFastener.id)
        )
    )
    inventory_rows = list(
        await session.scalars(
            select(RepairInventoryItem)
            .where(
                RepairInventoryItem.user_id == user_id,
                RepairInventoryItem.session_id == session_id,
            )
            .order_by(RepairInventoryItem.created_at, RepairInventoryItem.id)
        )
    )
    observation_rows = list(
        await session.scalars(
            select(RepairObservation)
            .where(
                RepairObservation.user_id == user_id,
                RepairObservation.session_id == session_id,
                RepairObservation.review_state == "confirmed",
            )
            .order_by(RepairObservation.created_at.desc(), RepairObservation.id.desc())
        )
    )
    photo_rows = list(
        await session.scalars(
            select(RepairPhotoEvidence)
            .where(
                RepairPhotoEvidence.user_id == user_id,
                RepairPhotoEvidence.session_id == session_id,
                RepairPhotoEvidence.deleted_at.is_(None),
            )
            .order_by(RepairPhotoEvidence.created_at.desc(), RepairPhotoEvidence.id.desc())
        )
    )
    location_rows = list(
        await session.scalars(
            select(RepairStorageLocation).where(
                RepairStorageLocation.user_id == user_id,
                RepairStorageLocation.session_id == session_id,
            )
        )
    )
    recent_events = list(
        await session.scalars(
            select(RepairSessionEvent)
            .where(
                RepairSessionEvent.user_id == user_id,
                RepairSessionEvent.session_id == session_id,
            )
            .order_by(RepairSessionEvent.sequence.desc())
            .limit(8)
        )
    )
    checkpoint_event = await session.scalar(
        select(RepairSessionEvent)
        .where(
            RepairSessionEvent.user_id == user_id,
            RepairSessionEvent.session_id == session_id,
            RepairSessionEvent.event_type.in_(DOMAIN_EVENT_TYPES),
        )
        .order_by(RepairSessionEvent.sequence.desc())
        .limit(1)
    )
    checkpoint_event = checkpoint_event or last_event

    fasteners = {row.id: row for row in fastener_rows}
    inventory = {row.id: row for row in inventory_rows}
    locations = {row.id: row for row in location_rows}
    observations = {row.id: row for row in observation_rows}

    attention: list[ResumeAttentionItemRead] = []
    for row in fastener_rows:
        if row.physical_state == "missing":
            attention.append(
                ResumeAttentionItemRead(
                    kind="fastener",
                    id=row.id,
                    label=row.label,
                    state="missing",
                    severity="blocking",
                    detail=row.origin or row.position,
                )
            )
        elif row.physical_state == "damaged":
            attention.append(
                ResumeAttentionItemRead(
                    kind="fastener",
                    id=row.id,
                    label=row.label,
                    state="damaged",
                    severity="attention",
                    detail=row.origin or row.position,
                )
            )

    for row in inventory_rows:
        if row.procurement_state in {"needed", "unavailable"}:
            attention.append(
                ResumeAttentionItemRead(
                    kind="inventory",
                    id=row.id,
                    label=row.name,
                    state=row.procurement_state,
                    severity="blocking",
                    detail=row.reference,
                )
            )
        elif row.procurement_state == "ordered":
            attention.append(
                ResumeAttentionItemRead(
                    kind="inventory",
                    id=row.id,
                    label=row.name,
                    state="ordered",
                    severity="waiting",
                    detail=row.reference,
                )
            )

    for row in observation_rows:
        if row.category == "damage":
            attention.append(
                ResumeAttentionItemRead(
                    kind="observation",
                    id=row.id,
                    label="Damage observation",
                    state="recorded",
                    severity="attention",
                    detail=row.text,
                )
            )

    storage_counts = Counter(
        row.storage_location_id
        for row in fastener_rows
        if row.physical_state == "stored" and row.storage_location_id is not None
    )
    storage_groups = [
        ResumeStorageGroupRead(
            storage_location_id=location_id,
            label=locations[location_id].label,
            item_count=count,
        )
        for location_id, count in storage_counts.most_common()
        if location_id in locations
    ]

    not_installed = sum(
        row.physical_state not in {"installed", "replaced"} for row in fastener_rows
    )
    stored = sum(row.physical_state == "stored" for row in fastener_rows)
    loose = sum(
        row.physical_state == "removed" and row.storage_location_id is None for row in fastener_rows
    )
    procurement_blockers = sum(
        row.procurement_state in {"needed", "ordered", "unavailable"} for row in inventory_rows
    )

    return RepairSessionReorientationRead(
        checkpoint=_activity(
            checkpoint_event,
            fasteners=fasteners,
            inventory=inventory,
            locations=locations,
            observations=observations,
        ),
        attention=attention,
        storage_groups=storage_groups,
        recent_observations=[
            ResumeObservationRead(
                id=row.id,
                category=row.category,
                text=row.text,
                fastener_id=row.fastener_id,
                created_at=row.created_at,
            )
            for row in observation_rows[:4]
        ],
        recent_evidence=[
            ResumeEvidenceRead(
                id=row.id,
                purpose=row.purpose,
                content_url=(
                    f"/api/v1/repair-sessions/{row.session_id}/photos/{row.id}/content"
                ),
                created_at=row.created_at,
            )
            for row in photo_rows[:4]
        ],
        recent_activity=[
            _activity(
                event,
                fasteners=fasteners,
                inventory=inventory,
                locations=locations,
                observations=observations,
            )
            for event in reversed(recent_events)
        ],
        counts=ResumeCountsRead(
            fasteners_total=len(fastener_rows),
            hardware_not_installed=not_installed,
            hardware_stored=stored,
            hardware_loose=loose,
            inventory_total=len(inventory_rows),
            procurement_blockers=procurement_blockers,
            observations_total=len(observation_rows),
            photos_total=len(photo_rows),
        ),
        next_verified_action=ResumeNextVerifiedActionRead(
            status="unavailable",
            reason="repair_plan_not_available",
        ),
    )
