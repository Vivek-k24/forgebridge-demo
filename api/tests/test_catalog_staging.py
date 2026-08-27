import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import text

from partgraph.catalog.service import (
    CatalogStagingError,
    StageRecordInput,
    complete_ingestion_batch,
    create_ingestion_batch,
    promote_verified_record,
    reject_staging_record,
    stage_source_record,
)
from partgraph.database import session_factory


def _record(source_record_id: str, *, revision: int = 1) -> StageRecordInput:
    return StageRecordInput(
        source_record_id=source_record_id,
        source_url=f"https://fixture.invalid/parts/{source_record_id}",
        fetched_at=datetime.now(UTC),
        observed_at=datetime(2026, 8, 27, 12, 0, tzinfo=UTC),
        candidate_type="part",
        raw_payload={
            "record_id": source_record_id,
            "revision": revision,
            "part_number": "FIXTURE-123",
        },
        candidate_payload={
            "part_number": "FIXTURE-123",
            "name": "Fixture radiator support",
        },
        vehicle_identity={
            "market": "US",
            "year": 2009,
            "make": "Honda",
            "model": "Civic",
        },
        provenance={
            "part_number": {"path": "fixture.part_number"},
            "name": {"path": "fixture.description"},
        },
        extraction_method="deterministic_fixture",
        confidence=0.99,
    )


def test_staging_deduplicates_identical_source_evidence_but_keeps_revisions() -> None:
    async def scenario() -> None:
        async with session_factory() as session:
            source_name = f"fixture-{uuid4().hex}"
            batch = await create_ingestion_batch(
                session,
                source_name=source_name,
                source_type="deterministic_fixture",
                collector_version="test-1",
            )
            source_record_id = f"row-{uuid4().hex}"
            first, first_created = await stage_source_record(
                session,
                batch_id=batch.id,
                record=_record(source_record_id),
            )
            duplicate, duplicate_created = await stage_source_record(
                session,
                batch_id=batch.id,
                record=_record(source_record_id),
            )
            revision, revision_created = await stage_source_record(
                session,
                batch_id=batch.id,
                record=_record(source_record_id, revision=2),
            )

            assert first_created is True
            assert duplicate_created is False
            assert duplicate.id == first.id
            assert revision_created is True
            assert revision.id != first.id
            assert revision.raw_sha256 != first.raw_sha256
            assert first.review_status == "pending"
            await session.rollback()

    asyncio.run(scenario())


def test_verified_promotion_is_explicit_idempotent_and_preserves_provenance() -> None:
    async def scenario() -> None:
        async with session_factory() as session:
            source_name = f"fixture-{uuid4().hex}"
            batch = await create_ingestion_batch(
                session,
                source_name=source_name,
                source_type="deterministic_fixture",
            )
            staged, _ = await stage_source_record(
                session,
                batch_id=batch.id,
                record=_record(f"row-{uuid4().hex}"),
            )

            evidence, created = await promote_verified_record(
                session,
                record_id=staged.id,
                reviewer="catalog-test-reviewer",
            )
            repeated, repeated_created = await promote_verified_record(
                session,
                record_id=staged.id,
                reviewer="catalog-test-reviewer",
            )

            assert created is True
            assert repeated_created is False
            assert repeated.id == evidence.id
            assert staged.review_status == "verified"
            assert staged.reviewed_by == "catalog-test-reviewer"
            assert evidence.source_name == source_name
            assert evidence.source_record_id == staged.source_record_id
            assert evidence.raw_sha256 == staged.raw_sha256
            assert evidence.verified_payload == staged.candidate_payload
            assert evidence.provenance == staged.provenance
            assert evidence.vehicle_identity == staged.vehicle_identity
            await session.rollback()

    asyncio.run(scenario())


def test_rejected_evidence_cannot_be_promoted_and_closed_batches_reject_new_records() -> None:
    async def scenario() -> None:
        async with session_factory() as session:
            batch = await create_ingestion_batch(
                session,
                source_name=f"fixture-{uuid4().hex}",
                source_type="deterministic_fixture",
            )
            staged, _ = await stage_source_record(
                session,
                batch_id=batch.id,
                record=_record(f"row-{uuid4().hex}"),
            )
            await reject_staging_record(
                session,
                record_id=staged.id,
                reviewer="catalog-test-reviewer",
            )

            try:
                await promote_verified_record(
                    session,
                    record_id=staged.id,
                    reviewer="catalog-test-reviewer",
                )
            except CatalogStagingError as exc:
                assert "rejected" in str(exc)
            else:
                raise AssertionError("rejected evidence was promoted")

            await complete_ingestion_batch(session, batch.id)
            try:
                await stage_source_record(
                    session,
                    batch_id=batch.id,
                    record=_record(f"row-{uuid4().hex}"),
                )
            except CatalogStagingError as exc:
                assert "not open" in str(exc)
            else:
                raise AssertionError("closed batch accepted a new staging record")
            await session.rollback()

    asyncio.run(scenario())


def test_collector_database_role_can_write_staging_but_not_canonical_tables() -> None:
    async def scenario() -> None:
        async with session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        has_schema_privilege('partgraph_collector', 'catalog_staging', 'USAGE'),
                        has_table_privilege(
                            'partgraph_collector',
                            'catalog_staging.source_records',
                            'INSERT'
                        ),
                        has_table_privilege(
                            'partgraph_collector',
                            'public.catalog_verified_evidence',
                            'INSERT'
                        ),
                        has_table_privilege(
                            'partgraph_collector',
                            'public.vehicle_configurations',
                            'INSERT'
                        )
                    """
                )
            )
            schema_usage, staging_insert, evidence_insert, vehicle_insert = result.one()
            assert schema_usage is True
            assert staging_insert is True
            assert evidence_insert is False
            assert vehicle_insert is False

    asyncio.run(scenario())
