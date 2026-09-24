from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..errors import ErrorCode, PartGraphError
from ..knowledge.extraction import ExtractionError, extract_and_stage_bound_provider_record
from ..knowledge.reference_parts import (
    ReferencePartsAdapter,
    ReferencePartsError,
    load_reference_parts_records,
)
from ..observability import emit_event
from .models import OperatorAuditEvent
from .schemas import ReferencePartsStageRead, ReferencePartsStageRequest

REFERENCE_DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "reference"


def _emit_ingestion_event(
    *,
    stage: str,
    outcome: str,
    level: int = logging.INFO,
    **attributes: object,
) -> None:
    emit_event(
        "provider.ingestion",
        level=level,
        **{
            "provider.name": "reference_parts",
            "partgraph.ingestion.mode": settings.provider_ingestion_mode,
            "stage": stage,
            "outcome": outcome,
            **attributes,
        },
    )


def _dataset_directory(dataset_key: str, *, reference_root: Path) -> Path:
    matches: list[Path] = []
    for manifest_path in sorted(reference_root.glob("*/manifest.json")):
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or "publication" not in payload:
            continue
        candidate = payload.get("dataset_key")
        if isinstance(candidate, str) and candidate.casefold() == dataset_key:
            matches.append(manifest_path.parent)

    if not matches:
        raise PartGraphError(
            code=ErrorCode.REQUEST_NOT_FOUND,
            message="Reviewed reference-parts dataset not found.",
            status_code=404,
        )
    if len(matches) > 1:
        raise PartGraphError(
            code=ErrorCode.REQUEST_CONFLICT,
            message="Reference-parts dataset key is not unique.",
            status_code=409,
        )
    return matches[0]


async def _validate_binding_semantics(
    session: AsyncSession,
    *,
    binding_id: UUID,
    expected_source_class: str,
) -> None:
    row = (
        await session.execute(
            text(
                """
                SELECT p.provider_kind, s.source_class
                FROM public.provider_source_bindings b
                JOIN public.provider_connections p
                  ON p.id = b.provider_connection_id
                JOIN public.catalog_sources s
                  ON s.id = b.source_id
                WHERE b.id = :binding_id
                """
            ),
            {"binding_id": binding_id},
        )
    ).mappings().one_or_none()
    if row is None:
        raise PartGraphError(
            code=ErrorCode.REQUEST_NOT_FOUND,
            message="Provider/source binding not found.",
            status_code=404,
        )
    if row["provider_kind"] != "internal_data":
        raise PartGraphError(
            code=ErrorCode.REQUEST_CONFLICT,
            message="Reviewed reference files require an internal-data provider binding.",
            status_code=409,
        )
    if row["source_class"] != expected_source_class:
        raise PartGraphError(
            code=ErrorCode.REQUEST_CONFLICT,
            message="Provider/source binding authority class does not match the dataset source class.",
            status_code=409,
        )


async def stage_reference_parts_dataset(
    session: AsyncSession,
    *,
    actor_id: UUID,
    payload: ReferencePartsStageRequest,
    reference_root: Path = REFERENCE_DATA_ROOT,
) -> ReferencePartsStageRead:
    try:
        dataset_directory = _dataset_directory(
            payload.dataset_key,
            reference_root=reference_root,
        )
    except PartGraphError as exc:
        _emit_ingestion_event(
            stage="dataset_resolution",
            outcome="blocked",
            level=logging.WARNING,
            **{"exception.type": type(exc).__name__},
        )
        raise

    try:
        prepared = load_reference_parts_records(dataset_directory)
    except ReferencePartsError as exc:
        _emit_ingestion_event(
            stage="dataset_validation",
            outcome="failure",
            level=logging.ERROR,
            **{"exception.type": type(exc).__name__},
        )
        raise PartGraphError(
            code=ErrorCode.REQUEST_CONFLICT,
            message="Reviewed reference-parts dataset failed its ingestion contract.",
            status_code=409,
        ) from exc

    required_classes = {record.source_class for record in prepared}
    provided_classes = set(payload.binding_ids)
    if required_classes != provided_classes:
        _emit_ingestion_event(
            stage="binding_validation",
            outcome="blocked",
            level=logging.WARNING,
            **{
                "partgraph.ingestion.required_binding_count": len(required_classes),
                "partgraph.ingestion.provided_binding_count": len(provided_classes),
            },
        )
        raise PartGraphError(
            code=ErrorCode.REQUEST_CONFLICT,
            message="A provider/source binding is required for every dataset source class and no others.",
            status_code=409,
            details={
                "required_source_classes": sorted(required_classes),
                "provided_source_classes": sorted(provided_classes),
            },
        )

    counts_by_class: dict[str, int] = {}
    for item in prepared:
        counts_by_class[item.source_class] = counts_by_class.get(item.source_class, 0) + 1

    for source_class in sorted(required_classes):
        binding_id = payload.binding_ids[source_class]
        try:
            await _validate_binding_semantics(
                session,
                binding_id=binding_id,
                expected_source_class=source_class,
            )
        except PartGraphError as exc:
            _emit_ingestion_event(
                stage="binding_validation",
                outcome="blocked",
                level=logging.WARNING,
                **{"exception.type": type(exc).__name__},
            )
            raise
        session.add(
            OperatorAuditEvent(
                id=uuid4(),
                actor_user_id=actor_id,
                action="reference_parts_dataset_staged",
                target_type="provider_source_binding",
                target_id=binding_id,
                event_data={
                    "dataset_key": payload.dataset_key,
                    "source_class": source_class,
                    "source_record_count": counts_by_class[source_class],
                    "publication_mode": "pending_candidates_only",
                },
            )
        )
    await session.flush()

    adapter = ReferencePartsAdapter()
    batch_ids: list[UUID] = []
    staging_ids: list[UUID] = []
    inserted_count = 0
    try:
        for item in prepared:
            result = await extract_and_stage_bound_provider_record(
                session,
                binding_id=payload.binding_ids[item.source_class],
                adapter=adapter,
                record=item.record,
            )
            batch_ids.append(result.ingestion_batch_id)
            staging_ids.extend(result.staging_record_ids)
            inserted_count += result.inserted_count
    except ExtractionError as exc:
        _emit_ingestion_event(
            stage="governed_staging",
            outcome="failure",
            level=logging.ERROR,
            **{"exception.type": type(exc).__name__},
        )
        raise PartGraphError(
            code=ErrorCode.REQUEST_CONFLICT,
            message="Reference-parts staging was blocked by provider/source governance.",
            status_code=409,
        ) from exc

    _emit_ingestion_event(
        stage="governed_staging",
        outcome="success",
        **{
            "partgraph.ingestion.source_record_count": len(prepared),
            "partgraph.ingestion.candidate_count": len(staging_ids),
            "partgraph.ingestion.inserted_count": inserted_count,
            "partgraph.ingestion.batch_count": len(batch_ids),
        },
    )
    return ReferencePartsStageRead(
        dataset_key=payload.dataset_key,
        source_record_count=len(prepared),
        candidate_count=len(staging_ids),
        inserted_count=inserted_count,
        ingestion_batch_ids=batch_ids,
        staging_record_ids=staging_ids,
    )
