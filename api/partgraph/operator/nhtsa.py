from __future__ import annotations

from urllib.parse import urlparse
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import ErrorCode, PartGraphError
from ..knowledge.extraction import ExtractionError, extract_and_stage_bound_provider_record
from ..knowledge.nhtsa import NhtsaRecallAdapter, NhtsaRecallCollector, NhtsaVehicleQuery
from .models import OperatorAuditEvent
from .schemas import NhtsaRecallStageRead, NhtsaRecallStageRequest


async def _validate_nhtsa_binding_semantics(
    session: AsyncSession,
    *,
    binding_id: UUID,
) -> None:
    row = (
        await session.execute(
            text(
                """
                SELECT p.provider_kind,
                       p.base_url,
                       s.source_key,
                       s.source_class
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
    if row["provider_kind"] != "vehicle_data":
        raise PartGraphError(
            code=ErrorCode.REQUEST_CONFLICT,
            message="NHTSA recall ingestion requires a vehicle-data provider binding.",
            status_code=409,
        )
    if row["source_class"] != "government" or row["source_key"] != "nhtsa-recalls":
        raise PartGraphError(
            code=ErrorCode.REQUEST_CONFLICT,
            message="NHTSA recall ingestion requires the registered NHTSA government source.",
            status_code=409,
        )

    parsed = urlparse(row["base_url"] or "")
    if parsed.scheme != "https" or parsed.hostname != "api.nhtsa.gov":
        raise PartGraphError(
            code=ErrorCode.REQUEST_CONFLICT,
            message="NHTSA recall ingestion requires a provider bound to api.nhtsa.gov.",
            status_code=409,
        )


async def stage_nhtsa_recall_query(
    session: AsyncSession,
    *,
    actor_id: UUID,
    payload: NhtsaRecallStageRequest,
    collector: NhtsaRecallCollector | None = None,
) -> NhtsaRecallStageRead:
    await _validate_nhtsa_binding_semantics(
        session,
        binding_id=payload.binding_id,
    )
    query = NhtsaVehicleQuery(payload.year, payload.make, payload.model)
    active_collector = collector or NhtsaRecallCollector()

    try:
        record = await active_collector.fetch(query)
    except ExtractionError as exc:
        raise PartGraphError(
            code=ErrorCode.REQUEST_CONFLICT,
            message="NHTSA recall acquisition failed validation or was unavailable.",
            status_code=409,
            retryable=True,
        ) from exc

    session.add(
        OperatorAuditEvent(
            id=uuid4(),
            actor_user_id=actor_id,
            action="nhtsa_recall_query_staged",
            target_type="provider_source_binding",
            target_id=payload.binding_id,
            event_data={
                "year": query.year,
                "make": query.normalized_make,
                "model": query.normalized_model,
                "publication_mode": "pending_candidates_only",
            },
        )
    )
    await session.flush()

    try:
        result = await extract_and_stage_bound_provider_record(
            session,
            binding_id=payload.binding_id,
            adapter=NhtsaRecallAdapter(),
            record=record,
        )
    except ExtractionError as exc:
        raise PartGraphError(
            code=ErrorCode.REQUEST_CONFLICT,
            message="NHTSA recall staging was blocked by provider/source governance.",
            status_code=409,
        ) from exc

    return NhtsaRecallStageRead(
        binding_id=payload.binding_id,
        year=query.year,
        make=query.normalized_make,
        model=query.normalized_model,
        candidate_count=len(result.staging_record_ids),
        inserted_count=result.inserted_count,
        ingestion_batch_id=result.ingestion_batch_id,
        staging_record_ids=list(result.staging_record_ids),
    )
