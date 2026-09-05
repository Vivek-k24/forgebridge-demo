"""Field-level reconciliation for progressively enriched vehicle specifications.

The staging boundary remains immutable. This module reads accepted source
observations, counts one vote per independent source per field, promotes
ordinary fields only after three matching sources, preserves conflicts, and
keeps manufacturer-authoritative service/fluid facts from being established by
three generic reference sites.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...knowledge.models import CatalogIngestionBatch, CatalogSourceRecord
from .specification_taxonomy import (
    normalize_observation_value,
    observation_comparison_key,
    section_summary,
)

VEHICLE_SPECIFICATION_CANDIDATE = "vehicle_specification_candidate"
ORDINARY_MATCH_THRESHOLD = 3
FieldKind = Literal["ordinary", "manufacturer_reported"]
_MANUFACTURER_SOURCE_CLASSES = {"manufacturer", "oem_service", "oem_parts"}
_MANUFACTURER_AUTHORITATIVE_PREFIXES = ("service.", "fluids.")


@dataclass(frozen=True, slots=True)
class FieldObservation:
    field: str
    value: object
    kind: FieldKind
    source_name: str
    source_class: str


def _set_nested(target: dict[str, object], dotted_field: str, value: object) -> None:
    parts = dotted_field.split(".")
    cursor: dict[str, object] = target
    for part in parts[:-1]:
        child = cursor.get(part)
        if not isinstance(child, dict):
            child = {}
            cursor[part] = child
        cursor = child
    cursor[parts[-1]] = value


def _rank_groups(
    field: str,
    observations: list[FieldObservation],
) -> list[list[FieldObservation]]:
    value_groups: dict[str, list[FieldObservation]] = defaultdict(list)
    for observation in observations:
        value_groups[observation_comparison_key(field, observation.value)].append(observation)
    return sorted(
        value_groups.values(),
        key=lambda group: (
            -len(group),
            observation_comparison_key(field, group[0].value),
        ),
    )


def _is_manufacturer_authoritative(field: str) -> bool:
    return field.startswith(_MANUFACTURER_AUTHORITATIVE_PREFIXES)


def reconcile_field_observations(
    observations: list[FieldObservation],
) -> dict[str, object]:
    """Reconcile observations without mutating canonical truth.

    One independent source receives one vote for one field. Repeated pages,
    reruns, or multiple records from the same source cannot satisfy the
    three-source threshold by themselves.
    """

    by_field_source: dict[str, dict[str, FieldObservation]] = defaultdict(dict)
    for observation in observations:
        by_field_source[observation.field][observation.source_name] = observation

    fields: list[dict[str, object]] = []
    promotable_patch: dict[str, object] = {}
    summary = {
        "verified_fields": 0,
        "manufacturer_reported_fields": 0,
        "candidate_fields": 0,
        "conflict_fields": 0,
    }

    for field in sorted(by_field_source):
        source_observations = list(by_field_source[field].values())
        ranked = _rank_groups(field, source_observations)
        winner = ranked[0]
        winner_count = len(winner)
        tied = len(ranked) > 1 and len(ranked[1]) == winner_count
        requires_manufacturer = _is_manufacturer_authoritative(field)

        manufacturer_observations = [
            observation
            for observation in source_observations
            if observation.source_class in _MANUFACTURER_SOURCE_CLASSES
        ]
        manufacturer_ranked = (
            _rank_groups(field, manufacturer_observations)
            if manufacturer_observations
            else []
        )
        manufacturer_winner = manufacturer_ranked[0] if manufacturer_ranked else []
        manufacturer_tied = (
            len(manufacturer_ranked) > 1
            and len(manufacturer_ranked[1]) == len(manufacturer_winner)
        )

        winner_has_explicit_manufacturer_report = any(
            observation.kind == "manufacturer_reported"
            and observation.source_class in _MANUFACTURER_SOURCE_CLASSES
            for observation in winner
        )

        selected_group = winner
        if requires_manufacturer:
            if not manufacturer_winner:
                decision = "conflict" if len(ranked) > 1 else "candidate"
            elif manufacturer_tied:
                decision = "conflict"
                selected_group = manufacturer_winner
            else:
                decision = "manufacturer_reported"
                selected_group = manufacturer_winner
        elif winner_count >= ORDINARY_MATCH_THRESHOLD and not tied:
            decision = "verified"
        elif winner_has_explicit_manufacturer_report and not tied:
            decision = "manufacturer_reported"
        elif len(ranked) > 1:
            decision = "conflict"
        else:
            decision = "candidate"

        selected_value: object | None = None
        if decision in {"verified", "manufacturer_reported"}:
            selected_value = normalize_observation_value(field, selected_group[0].value)
            _set_nested(promotable_patch, field, selected_value)

        selected_key = observation_comparison_key(field, selected_group[0].value)
        conflicts = [
            {
                "value": normalize_observation_value(field, group[0].value),
                "match_count": len(group),
                "sources": sorted(item.source_name for item in group),
            }
            for group in ranked
            if observation_comparison_key(field, group[0].value) != selected_key
        ]

        summary_key = {
            "verified": "verified_fields",
            "manufacturer_reported": "manufacturer_reported_fields",
            "candidate": "candidate_fields",
            "conflict": "conflict_fields",
        }[decision]
        summary[summary_key] += 1

        fields.append(
            {
                "field": field,
                "kind": (
                    "manufacturer_reported"
                    if requires_manufacturer or winner_has_explicit_manufacturer_report
                    else "ordinary"
                ),
                "status": decision,
                "selected_value": selected_value,
                "match_count": len(selected_group),
                "sources": sorted(item.source_name for item in selected_group),
                "conflicts": conflicts,
                "authority": (
                    "manufacturer_required"
                    if requires_manufacturer
                    else "ordinary_three_source"
                ),
            }
        )

    return {
        "rule": {
            "ordinary_min_independent_sources": ORDINARY_MATCH_THRESHOLD,
            "source_vote_policy": "one vote per independent source per field",
            "source_count_policy": (
                "no fixed maximum; collect additional independent sources as needed"
            ),
            "manufacturer_reported_policy": (
                "manufacturer-authoritative fields may be retained from one applicable "
                "manufacturer source and remain labeled manufacturer_reported"
            ),
            "manufacturer_authoritative_prefixes": list(
                _MANUFACTURER_AUTHORITATIVE_PREFIXES
            ),
        },
        "summary": summary,
        "sections": section_summary(fields),
        "fields": fields,
        "promotable_profile_patch": promotable_patch,
    }


def _record_observations(
    record: CatalogSourceRecord,
    batch: CatalogIngestionBatch,
) -> list[FieldObservation]:
    fields = record.candidate_payload.get("fields")
    if not isinstance(fields, dict):
        return []
    source_class = record.provenance.get("source_class", "unknown")
    if not isinstance(source_class, str):
        source_class = "unknown"

    observations: list[FieldObservation] = []
    for field, payload in fields.items():
        if not isinstance(field, str) or not isinstance(payload, dict) or "value" not in payload:
            continue
        raw_kind = payload.get("kind", "ordinary")
        kind: FieldKind = (
            "manufacturer_reported"
            if raw_kind == "manufacturer_reported"
            else "ordinary"
        )
        observations.append(
            FieldObservation(
                field=field,
                value=payload["value"],
                kind=kind,
                source_name=batch.source_name,
                source_class=source_class,
            )
        )
    return observations


async def reconcile_vehicle_specification_profile(
    session: AsyncSession,
    configuration_id: UUID,
) -> dict[str, object]:
    rows = (
        await session.execute(
            select(CatalogSourceRecord, CatalogIngestionBatch)
            .join(CatalogIngestionBatch, CatalogSourceRecord.batch_id == CatalogIngestionBatch.id)
            .where(
                CatalogSourceRecord.candidate_type == VEHICLE_SPECIFICATION_CANDIDATE,
                CatalogSourceRecord.review_status == "verified",
                CatalogSourceRecord.vehicle_identity[
                    "vehicle_configuration_id"
                ].astext
                == str(configuration_id),
            )
            .order_by(CatalogSourceRecord.fetched_at, CatalogSourceRecord.created_at)
        )
    ).all()

    observations: list[FieldObservation] = []
    for record, batch in rows:
        observations.extend(_record_observations(record, batch))

    result = reconcile_field_observations(observations)
    result["vehicle_configuration_id"] = str(configuration_id)
    result["observation_records"] = len(rows)
    result["independent_sources"] = len({batch.source_name for _, batch in rows})
    return result
