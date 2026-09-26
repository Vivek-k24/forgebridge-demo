import os
import unittest
from uuid import UUID, uuid4

import psycopg
from sqlalchemy import text

from partgraph.database import session_factory
from partgraph.knowledge.part_catalog_materialization import (
    resolve_part_fitment_claim_payload,
)

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
MATERIALIZER_ROLE = "partgraph_materializer"


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


class PartCatalogMaterializationDatabaseTests(unittest.IsolatedAsyncioTestCase):
    vehicle_id: UUID

    async def asyncSetUp(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")
        self.vehicle_id = uuid4()
        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.vehicle_configurations
                        (id, identity_hash, base_identity_hash, canonicalization_version,
                         year, market, make, model, identity_source, verification_status)
                    VALUES (%s, %s, %s, 3, 2024, 'US', 'Fixture', 'Parts',
                            'fixture', 'verified')
                    """,
                    (self.vehicle_id, uuid4().hex * 2, uuid4().hex * 2),
                )

    async def asyncTearDown(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            return
        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM public.vehicle_configurations WHERE id = %s",
                    (self.vehicle_id,),
                )

    async def test_inline_identity_creates_component_part_and_role_idempotently(self) -> None:
        suffix = uuid4().hex[:10]
        payload = {
            "component": {
                "component_key": f"fixture.cooling.radiator.{suffix}",
                "display_name": "Radiator assembly",
            },
            "part": {
                "manufacturer": "Fixture OEM",
                "part_number": f"RAD-{suffix}",
                "revision": "",
                "display_name": "Radiator assembly",
            },
            "position_key": "front",
            "applicability_state": "applicable",
            "qualifier_key": "",
            "qualifiers": {},
        }
        async with session_factory() as session:
            async with session.begin():
                await session.execute(text(f"SET LOCAL ROLE {MATERIALIZER_ROLE}"))
                first = await resolve_part_fitment_claim_payload(session, payload)
        async with session_factory() as session:
            async with session.begin():
                await session.execute(text(f"SET LOCAL ROLE {MATERIALIZER_ROLE}"))
                second = await resolve_part_fitment_claim_payload(session, payload)
        self.assertEqual(first.component_part_role_id, second.component_part_role_id)

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT c.component_key, p.manufacturer, p.part_number, r.position_key
                    FROM public.component_part_roles r
                    JOIN public.component_definitions c ON c.id = r.component_id
                    JOIN public.part_identities p ON p.id = r.part_id
                    WHERE r.id = %s
                    """,
                    (first.component_part_role_id,),
                )
                row = cursor.fetchone()
                self.assertEqual(row[0], payload["component"]["component_key"])
                self.assertEqual(row[1], "Fixture OEM")
                self.assertEqual(row[2], f"RAD-{suffix}")
                self.assertEqual(row[3], "front")
                cursor.execute(
                    "DELETE FROM public.component_part_roles WHERE id = %s",
                    (first.component_part_role_id,),
                )
                cursor.execute(
                    "DELETE FROM public.component_definitions WHERE component_key = %s",
                    (payload["component"]["component_key"],),
                )
                cursor.execute(
                    "DELETE FROM public.part_identities WHERE manufacturer = %s AND part_number = %s",
                    ("Fixture OEM", f"RAD-{suffix}"),
                )


if __name__ == "__main__":
    unittest.main()
