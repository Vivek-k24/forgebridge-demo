import os
import unittest
from datetime import UTC, datetime
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb
from sqlalchemy import text

from partgraph.database import session_factory
from partgraph.errors import ErrorCode, PartGraphError
from partgraph.knowledge.procedure_service import verified_procedure_plan
from partgraph.knowledge.repair_materialization_contract import (
    RepairDefinitionMaterializationCreate,
)
from partgraph.knowledge.repair_materialization_service import (
    materialize_repair_definition_service,
)
from partgraph.knowledge.repair_service import verified_requirement_manifest

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
MATERIALIZER_ROLE = "partgraph_materializer"


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


class RepairMaterializationDatabaseTests(unittest.IsolatedAsyncioTestCase):
    vehicle_id: UUID
    source_id: UUID
    requirement_claim_id: UUID
    procedure_claim_id: UUID
    repair_key: str
    requirement_key: str

    async def asyncSetUp(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")

        self.vehicle_id = uuid4()
        self.source_id = uuid4()
        self.requirement_claim_id = uuid4()
        self.procedure_claim_id = uuid4()
        suffix = uuid4().hex[:12]
        self.repair_key = f"fixture.cover-remove-{suffix}"
        self.requirement_key = f"tool.fixture-socket-{suffix}"
        source_key = f"materialization-test-{suffix}"
        requirement_evidence_id = uuid4()
        procedure_evidence_id = uuid4()
        now = datetime.now(UTC)

        requirement_payload = {
            "requirement_key": self.requirement_key,
            "category": "tool",
            "display_name": "Fixture socket",
            "necessity": "required",
            "fulfillment_mode": "reusable",
            "timing": "operation",
            "operation_key": "remove-cover",
        }
        procedure_payload = {
            "action_key": "remove-cover",
            "title": "Remove fixture cover",
            "instruction": "Remove the fixture cover fasteners.",
            "position": 0,
            "skippable": False,
            "requirement_use_keys": ["socket-use"],
        }

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.vehicle_configurations
                        (id, identity_hash, base_identity_hash, canonicalization_version,
                         year, market, make, model, identity_source, verification_status)
                    VALUES (%s, %s, %s, 2, 2024, 'test', 'Fixture', 'Materializer',
                            'fixture', 'verified')
                    """,
                    (self.vehicle_id, uuid4().hex * 2, uuid4().hex * 2),
                )
                cursor.execute(
                    """
                    INSERT INTO public.catalog_sources
                        (id, source_key, display_name, source_class,
                         license_status, automation_allowed)
                    VALUES (%s, %s, 'Materialization fixture source',
                            'oem_service', 'approved', false)
                    """,
                    (self.source_id, source_key),
                )
                for evidence_id, record_id, payload in (
                    (requirement_evidence_id, "requirement", requirement_payload),
                    (procedure_evidence_id, "procedure", procedure_payload),
                ):
                    cursor.execute(
                        """
                        INSERT INTO public.catalog_verified_evidence
                            (id, staging_record_id, candidate_type, verified_payload,
                             vehicle_identity, source_name, source_type, source_record_id,
                             source_url, raw_sha256, fetched_at, provenance,
                             extraction_method, promoted_by)
                        VALUES (%s, %s, 'mechanical_claim_candidate', %s, %s,
                                %s, 'oem_service', %s, %s, %s, %s, %s,
                                'fixture', 'fixture-reviewer')
                        """,
                        (
                            evidence_id,
                            uuid4(),
                            Jsonb({"mechanical_claim": payload}),
                            Jsonb({"vehicle_configuration_id": str(self.vehicle_id)}),
                            source_key,
                            record_id,
                            f"https://example.invalid/materialization/{record_id}",
                            uuid4().hex * 2,
                            now,
                            Jsonb({"fixture": True}),
                        ),
                    )
                cursor.execute(
                    """
                    INSERT INTO public.mechanical_claims
                        (id, source_id, verified_evidence_id, vehicle_configuration_id,
                         claim_domain, claim_risk, normalized_key, repair_key,
                         claim_payload, explicit_claim, exact_applicability,
                         promotion_state, reviewed_at, reviewed_by)
                    VALUES (%s, %s, %s, %s, 'repair_requirement', 'normal',
                            %s, %s, %s, true, true, 'verified', %s, 'fixture-curator')
                    """,
                    (
                        self.requirement_claim_id,
                        self.source_id,
                        requirement_evidence_id,
                        self.vehicle_id,
                        self.requirement_key,
                        self.repair_key,
                        Jsonb(requirement_payload),
                        now,
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO public.mechanical_claims
                        (id, source_id, verified_evidence_id, vehicle_configuration_id,
                         claim_domain, claim_risk, normalized_key, repair_key,
                         claim_payload, explicit_claim, exact_applicability,
                         promotion_state, reviewed_at, reviewed_by)
                    VALUES (%s, %s, %s, %s, 'repair_procedure', 'normal',
                            'remove-cover', %s, %s, true, true, 'verified',
                            %s, 'fixture-curator')
                    """,
                    (
                        self.procedure_claim_id,
                        self.source_id,
                        procedure_evidence_id,
                        self.vehicle_id,
                        self.repair_key,
                        Jsonb(procedure_payload),
                        now,
                    ),
                )

    def _request(
        self,
        *,
        title: str,
        expected_current_definition_id: UUID | None = None,
    ) -> RepairDefinitionMaterializationCreate:
        return RepairDefinitionMaterializationCreate(
            vehicle_configuration_id=self.vehicle_id,
            repair_key=self.repair_key,
            title=title,
            capability_policy_key="diy_supported",
            expected_current_definition_id=expected_current_definition_id,
            operations=[
                {
                    "operation_key": "remove-cover",
                    "label": "Remove fixture cover",
                    "position": 0,
                }
            ],
            requirements=[
                {
                    "use_key": "socket-use",
                    "requirement_key": self.requirement_key,
                    "category": "tool",
                    "display_name": "Fixture socket",
                    "necessity": "required",
                    "fulfillment_mode": "reusable",
                    "timing": "operation",
                    "operation_key": "remove-cover",
                    "supporting_claim_ids": [self.requirement_claim_id],
                }
            ],
            actions=[
                {
                    "action_key": "remove-cover",
                    "title": "Remove fixture cover",
                    "instruction": "Remove the fixture cover fasteners.",
                    "position": 0,
                    "skippable": False,
                    "requirement_use_keys": ["socket-use"],
                    "supporting_claim_ids": [self.procedure_claim_id],
                }
            ],
        )

    async def _publish(
        self,
        request: RepairDefinitionMaterializationCreate,
        idempotency_key: str,
    ):
        async with session_factory() as session:
            async with session.begin():
                await session.execute(text(f"SET LOCAL ROLE {MATERIALIZER_ROLE}"))
                return await materialize_repair_definition_service(
                    session,
                    request=request,
                    actor="fixture-curator:curator",
                    idempotency_key=idempotency_key,
                )

    async def test_materialization_is_idempotent_versioned_and_runtime_readable(self) -> None:
        first_request = self._request(title="Fixture cover removal")
        first_key = f"repair:test:{uuid4().hex}"
        first = await self._publish(first_request, first_key)
        self.assertEqual(first.version, 1)
        self.assertEqual(first.definition_status, "verified")
        self.assertFalse(first.idempotent)

        repeated = await self._publish(first_request, first_key)
        self.assertTrue(repeated.idempotent)
        self.assertEqual(repeated.repair_definition_id, first.repair_definition_id)
        self.assertEqual(
            repeated.canonical_record_version_id,
            first.canonical_record_version_id,
        )

        conflicting_retry = first_request.model_copy(update={"title": "Different request"})
        with self.assertRaises(PartGraphError) as context:
            await self._publish(conflicting_retry, first_key)
        self.assertEqual(
            context.exception.code,
            ErrorCode.KNOWLEDGE_PUBLICATION_IDEMPOTENCY_CONFLICT,
        )

        second_request = self._request(
            title="Fixture cover removal revised",
            expected_current_definition_id=first.repair_definition_id,
        )
        second = await self._publish(second_request, f"repair:test:{uuid4().hex}")
        self.assertEqual(second.version, 2)
        self.assertEqual(second.superseded_definition_id, first.repair_definition_id)

        async with session_factory() as session:
            manifest = await verified_requirement_manifest(
                session,
                vehicle_configuration_id=self.vehicle_id,
                repair_key=self.repair_key,
            )
            procedure = await verified_procedure_plan(
                session,
                vehicle_configuration_id=self.vehicle_id,
                repair_key=self.repair_key,
            )
        self.assertEqual(manifest.version, 2)
        self.assertEqual(procedure.version, 2)
        self.assertEqual(len(manifest.requirements), 1)
        self.assertEqual(len(procedure.actions), 1)
        self.assertEqual(
            manifest.requirements[0].supporting_claim_ids,
            [self.requirement_claim_id],
        )
        self.assertEqual(
            procedure.actions[0].supporting_claim_ids,
            [self.procedure_claim_id],
        )

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT version, status, superseded_by_id
                    FROM public.repair_definitions
                    WHERE vehicle_configuration_id = %s AND repair_key = %s
                    ORDER BY version
                    """,
                    (self.vehicle_id, self.repair_key),
                )
                rows = cursor.fetchall()
                self.assertEqual(rows[0], (1, "superseded", second.repair_definition_id))
                self.assertEqual(rows[1], (2, "verified", None))

                cursor.execute(
                    """
                    SELECT version, publication_state, supersedes_version_id
                    FROM public.canonical_record_versions
                    WHERE canonical_domain = 'repair'
                      AND record_type = 'repair_definition'
                      AND record_id IN (%s, %s)
                    ORDER BY version
                    """,
                    (first.repair_definition_id, second.repair_definition_id),
                )
                publication_rows = cursor.fetchall()
                self.assertEqual(publication_rows[0][0:2], (1, "superseded"))
                self.assertEqual(publication_rows[1][0:2], (2, "verified"))
                self.assertEqual(
                    publication_rows[1][2],
                    first.canonical_record_version_id,
                )


if __name__ == "__main__":
    unittest.main()
