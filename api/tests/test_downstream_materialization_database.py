import os
import unittest
from datetime import UTC, datetime
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb
from sqlalchemy import text

from partgraph.database import session_factory
from partgraph.errors import PartGraphError
from partgraph.knowledge.downstream_materialization import (
    DownstreamRequirementMaterializationCreate,
    materialize_downstream_requirement_service,
)

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
MATERIALIZER_ROLE = "partgraph_materializer"


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


class DownstreamMaterializationDatabaseTests(unittest.IsolatedAsyncioTestCase):
    vehicle_id: UUID
    source_definition_id: UUID
    target_definition_id: UUID
    trigger_action_id: UUID
    claim_id: UUID

    async def asyncSetUp(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")

        suffix = uuid4().hex[:12]
        self.vehicle_id = uuid4()
        self.source_definition_id = uuid4()
        self.target_definition_id = uuid4()
        self.trigger_action_id = uuid4()
        self.claim_id = uuid4()
        self.source_repair_key = f"fixture.replace-component-{suffix}"
        self.target_repair_key = f"fixture.follow-up-operation-{suffix}"
        self.requirement_key = f"fixture.follow-up-required-{suffix}"
        self.source_id = uuid4()
        evidence_id = uuid4()
        now = datetime.now(UTC)
        self.claim_payload = {
            "downstream_requirement_key": self.requirement_key,
            "downstream_title": "Complete required follow-up operation",
            "downstream_detail": "The replacement is not mechanically complete until the follow-up is done.",
            "downstream_trigger_type": "action_completed",
            "downstream_trigger_action_key": "replace-component",
            "downstream_support_state": "supported",
            "downstream_target_repair_key": self.target_repair_key,
            "milestone_type": "physical_replacement",
        }

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.vehicle_configurations
                        (id, identity_hash, base_identity_hash, canonicalization_version,
                         year, market, make, model, identity_source, verification_status)
                    VALUES (%s, %s, %s, 2, 2024, 'test', 'Fixture', 'Downstream',
                            'fixture', 'verified')
                    """,
                    (self.vehicle_id, uuid4().hex * 2, uuid4().hex * 2),
                )
                cursor.execute(
                    """
                    INSERT INTO public.catalog_sources
                        (id, source_key, display_name, source_class,
                         license_status, automation_allowed)
                    VALUES (%s, %s, 'Downstream materialization fixture',
                            'oem_service', 'approved', false)
                    """,
                    (self.source_id, f"downstream-test-{suffix}"),
                )
                for definition_id, repair_key, title in (
                    (
                        self.source_definition_id,
                        self.source_repair_key,
                        "Replace fixture component",
                    ),
                    (
                        self.target_definition_id,
                        self.target_repair_key,
                        "Fixture follow-up operation",
                    ),
                ):
                    cursor.execute(
                        """
                        INSERT INTO public.repair_definitions
                            (id, vehicle_configuration_id, repair_key, title,
                             version, status, verified_at)
                        VALUES (%s, %s, %s, %s, 1, 'verified', %s)
                        """,
                        (definition_id, self.vehicle_id, repair_key, title, now),
                    )
                cursor.execute(
                    """
                    INSERT INTO public.procedure_actions
                        (id, repair_definition_id, action_key, title, instruction,
                         position, skippable)
                    VALUES (%s, %s, 'replace-component', 'Replace component',
                            'Replace the fixture component.', 0, false)
                    """,
                    (self.trigger_action_id, self.source_definition_id),
                )
                cursor.execute(
                    """
                    INSERT INTO public.catalog_verified_evidence
                        (id, staging_record_id, candidate_type, verified_payload,
                         vehicle_identity, source_name, source_type, source_record_id,
                         source_url, raw_sha256, fetched_at, provenance,
                         extraction_method, promoted_by)
                    VALUES (%s, %s, 'mechanical_claim_candidate', %s, %s,
                            %s, 'oem_service', 'downstream', %s, %s, %s, %s,
                            'fixture', 'fixture-reviewer')
                    """,
                    (
                        evidence_id,
                        uuid4(),
                        Jsonb({"mechanical_claim": self.claim_payload}),
                        Jsonb({"vehicle_configuration_id": str(self.vehicle_id)}),
                        f"downstream-test-{suffix}",
                        "https://example.invalid/downstream",
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
                    VALUES (%s, %s, %s, %s, 'repair_procedure', 'safety_critical',
                            %s, %s, %s, true, true, 'verified', %s, 'fixture-curator')
                    """,
                    (
                        self.claim_id,
                        self.source_id,
                        evidence_id,
                        self.vehicle_id,
                        f"downstream.{self.requirement_key}",
                        self.source_repair_key,
                        Jsonb(self.claim_payload),
                        now,
                    ),
                )

    def _request(
        self,
        *,
        target_repair_definition_id: UUID | None = None,
    ) -> DownstreamRequirementMaterializationCreate:
        return DownstreamRequirementMaterializationCreate(
            source_repair_definition_id=self.source_definition_id,
            requirement_key=self.requirement_key,
            title="Complete required follow-up operation",
            detail=(
                "The replacement is not mechanically complete until the follow-up is done."
            ),
            trigger_type="action_completed",
            trigger_action_key="replace-component",
            support_state="supported",
            target_repair_definition_id=(
                self.target_definition_id
                if target_repair_definition_id is None
                else target_repair_definition_id
            ),
            milestone_type="physical_replacement",
            position=0,
            supporting_claim_ids=[self.claim_id],
        )

    async def _publish(self, request: DownstreamRequirementMaterializationCreate):
        async with session_factory() as session:
            async with session.begin():
                await session.execute(text(f"SET LOCAL ROLE {MATERIALIZER_ROLE}"))
                return await materialize_downstream_requirement_service(
                    session,
                    request=request,
                )

    async def test_verified_downstream_rule_is_append_only_and_idempotent(self) -> None:
        request = self._request()
        first = await self._publish(request)
        self.assertFalse(first.idempotent)
        self.assertEqual(first.trigger_action_id, self.trigger_action_id)
        self.assertEqual(first.target_repair_definition_id, self.target_definition_id)
        self.assertEqual(first.milestone_type, "physical_replacement")
        self.assertEqual(first.supporting_claim_ids, [self.claim_id])

        repeated = await self._publish(request)
        self.assertTrue(repeated.idempotent)
        self.assertEqual(
            repeated.downstream_requirement_id,
            first.downstream_requirement_id,
        )

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT milestone_type
                    FROM public.procedure_action_milestones
                    WHERE action_id = %s
                    """,
                    (self.trigger_action_id,),
                )
                self.assertEqual(cursor.fetchone(), ("physical_replacement",))

                cursor.execute(
                    """
                    SELECT requirement_key, trigger_type, trigger_action_id,
                           support_state, target_repair_definition_id, position
                    FROM public.repair_downstream_requirements
                    WHERE id = %s
                    """,
                    (first.downstream_requirement_id,),
                )
                self.assertEqual(
                    cursor.fetchone(),
                    (
                        self.requirement_key,
                        "action_completed",
                        self.trigger_action_id,
                        "supported",
                        self.target_definition_id,
                        0,
                    ),
                )
                cursor.execute(
                    """
                    SELECT mechanical_claim_id
                    FROM public.repair_downstream_requirement_evidence
                    WHERE downstream_requirement_id = %s
                    """,
                    (first.downstream_requirement_id,),
                )
                self.assertEqual(cursor.fetchall(), [(self.claim_id,)])

    async def test_target_must_match_source_exact_vehicle(self) -> None:
        other_vehicle_id = uuid4()
        other_target_id = uuid4()
        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.vehicle_configurations
                        (id, identity_hash, base_identity_hash, canonicalization_version,
                         year, market, make, model, identity_source, verification_status)
                    VALUES (%s, %s, %s, 2, 2024, 'test', 'Fixture', 'Other',
                            'fixture', 'verified')
                    """,
                    (other_vehicle_id, uuid4().hex * 2, uuid4().hex * 2),
                )
                cursor.execute(
                    """
                    INSERT INTO public.repair_definitions
                        (id, vehicle_configuration_id, repair_key, title,
                         version, status, verified_at)
                    VALUES (%s, %s, %s, 'Other follow-up', 1, 'verified', %s)
                    """,
                    (other_target_id, other_vehicle_id, self.target_repair_key, datetime.now(UTC)),
                )

        with self.assertRaises(PartGraphError):
            await self._publish(
                self._request(target_repair_definition_id=other_target_id)
            )


if __name__ == "__main__":
    unittest.main()
