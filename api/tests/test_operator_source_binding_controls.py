import os
import unittest
from uuid import UUID, uuid4

import psycopg
from pydantic import ValidationError

from partgraph.database import session_factory
from partgraph.errors import PartGraphError
from partgraph.identity.auth.roles import assume_operator_database_role
from partgraph.operator.schemas import (
    CatalogSourceCreate,
    CatalogSourceUpdate,
    ProviderCreate,
    ProviderSourceBindingCreate,
    ProviderSourceBindingUpdate,
    ProviderUpdate,
)
from partgraph.operator.service import (
    create_catalog_source,
    create_provider,
    create_provider_source_binding,
    update_catalog_source,
    update_provider,
    update_provider_source_binding,
)

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
APP_ROLE = "partgraph_app"
OPERATOR_ROLE = "partgraph_operator"


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


class OperatorSourceBindingSchemaTests(unittest.TestCase):
    def test_source_automation_requires_approved_license(self) -> None:
        with self.assertRaises(ValidationError):
            CatalogSourceCreate(
                source_key="fixture-source",
                display_name="Fixture source",
                source_class="government",
                license_status="unreviewed",
                automation_allowed=True,
            )


class OperatorSourceBindingPrivilegeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")
        cls.connection = psycopg.connect(_database_url())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.connection.close()

    def _table_privilege(self, role: str, table: str, privilege: str) -> bool:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT has_table_privilege(%s, %s, %s)",
                (role, table, privilege),
            )
            row = cursor.fetchone()
            assert row is not None
            return bool(row[0])

    def test_app_is_read_only_while_operator_manages_source_registry(self) -> None:
        for table in (
            "public.catalog_sources",
            "public.provider_source_bindings",
        ):
            with self.subTest(role=APP_ROLE, table=table):
                self.assertTrue(self._table_privilege(APP_ROLE, table, "SELECT"))
                self.assertFalse(self._table_privilege(APP_ROLE, table, "INSERT"))
                self.assertFalse(self._table_privilege(APP_ROLE, table, "UPDATE"))
                self.assertFalse(self._table_privilege(APP_ROLE, table, "DELETE"))

            with self.subTest(role=OPERATOR_ROLE, table=table):
                self.assertTrue(self._table_privilege(OPERATOR_ROLE, table, "SELECT"))
                self.assertTrue(self._table_privilege(OPERATOR_ROLE, table, "INSERT"))
                self.assertTrue(self._table_privilege(OPERATOR_ROLE, table, "UPDATE"))
                self.assertFalse(self._table_privilege(OPERATOR_ROLE, table, "DELETE"))

        for role in (APP_ROLE, OPERATOR_ROLE):
            for privilege in ("INSERT", "UPDATE", "DELETE"):
                with self.subTest(role=role, privilege=privilege):
                    self.assertFalse(
                        self._table_privilege(
                            role,
                            "public.source_authority_policies",
                            privilege,
                        )
                    )


class OperatorSourceBindingServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")

        self.actor_id = uuid4()
        unique = self.actor_id.hex
        self.provider_id: UUID | None = None
        self.source_id: UUID | None = None
        self.binding_id: UUID | None = None
        self.provider_key = f"admin-provider-{unique}"
        self.source_key = f"admin-source-{unique}"

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.users
                        (id, email, username, password_hash, role, is_active)
                    VALUES (%s, %s, %s, 'fixture-hash', 'operator_admin', true)
                    """,
                    (
                        self.actor_id,
                        f"operator-source-{unique}@example.invalid",
                        f"opsrc_{unique[:20]}",
                    ),
                )
                cursor.execute("SELECT count(*) FROM catalog_staging.source_records")
                row = cursor.fetchone()
                assert row is not None
                self.staging_count_before = int(row[0])
            connection.commit()

    async def asyncTearDown(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            return
        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM public.operator_audit_events WHERE actor_user_id = %s",
                    (self.actor_id,),
                )
                if self.binding_id is not None:
                    cursor.execute(
                        "DELETE FROM public.provider_source_bindings WHERE id = %s",
                        (self.binding_id,),
                    )
                if self.provider_id is not None:
                    cursor.execute(
                        "DELETE FROM public.provider_connections WHERE id = %s",
                        (self.provider_id,),
                    )
                if self.source_id is not None:
                    cursor.execute(
                        "DELETE FROM public.catalog_sources WHERE id = %s",
                        (self.source_id,),
                    )
                cursor.execute(
                    "DELETE FROM public.users WHERE id = %s",
                    (self.actor_id,),
                )
            connection.commit()

    async def test_binding_enablement_is_explicit_fail_closed_and_does_not_collect(self) -> None:
        async with session_factory() as db:
            async with db.begin():
                await assume_operator_database_role(db)
                provider = await create_provider(
                    db,
                    actor_id=self.actor_id,
                    payload=ProviderCreate(
                        provider_key=self.provider_key,
                        display_name="Admin provider fixture",
                        provider_kind="internal_data",
                        enabled=False,
                        capabilities=["mechanical_claim_candidates"],
                    ),
                )
                self.provider_id = provider.id

                source = await create_catalog_source(
                    db,
                    actor_id=self.actor_id,
                    payload=CatalogSourceCreate(
                        source_key=self.source_key,
                        display_name="Admin source fixture",
                        source_class="government",
                        license_status="unreviewed",
                        automation_allowed=False,
                    ),
                )
                self.source_id = source.id

                binding = await create_provider_source_binding(
                    db,
                    actor_id=self.actor_id,
                    payload=ProviderSourceBindingCreate(
                        provider_connection_id=provider.id,
                        source_id=source.id,
                        enabled=False,
                    ),
                )
                self.binding_id = binding.id
                self.assertFalse(binding.enabled)
                self.assertFalse(binding.ready_for_ingestion)

                with self.assertRaises(PartGraphError):
                    await update_provider_source_binding(
                        db,
                        actor_id=self.actor_id,
                        binding_id=binding.id,
                        payload=ProviderSourceBindingUpdate(enabled=True),
                    )

                provider = await update_provider(
                    db,
                    actor_id=self.actor_id,
                    provider_id=provider.id,
                    payload=ProviderUpdate(enabled=True),
                )
                self.assertTrue(provider.enabled)

                with self.assertRaises(PartGraphError):
                    await update_provider_source_binding(
                        db,
                        actor_id=self.actor_id,
                        binding_id=binding.id,
                        payload=ProviderSourceBindingUpdate(enabled=True),
                    )

                source = await update_catalog_source(
                    db,
                    actor_id=self.actor_id,
                    source_id=source.id,
                    payload=CatalogSourceUpdate(license_status="approved"),
                )
                self.assertEqual(source.license_status, "approved")
                self.assertFalse(source.automation_allowed)

                with self.assertRaises(PartGraphError):
                    await update_provider_source_binding(
                        db,
                        actor_id=self.actor_id,
                        binding_id=binding.id,
                        payload=ProviderSourceBindingUpdate(enabled=True),
                    )

                source = await update_catalog_source(
                    db,
                    actor_id=self.actor_id,
                    source_id=source.id,
                    payload=CatalogSourceUpdate(automation_allowed=True),
                )
                self.assertTrue(source.automation_allowed)

                binding = await update_provider_source_binding(
                    db,
                    actor_id=self.actor_id,
                    binding_id=binding.id,
                    payload=ProviderSourceBindingUpdate(enabled=True),
                )
                self.assertTrue(binding.enabled)
                self.assertTrue(binding.ready_for_ingestion)

                binding = await update_provider_source_binding(
                    db,
                    actor_id=self.actor_id,
                    binding_id=binding.id,
                    payload=ProviderSourceBindingUpdate(enabled=False),
                )
                self.assertFalse(binding.enabled)
                self.assertFalse(binding.ready_for_ingestion)

        with psycopg.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM catalog_staging.source_records")
                row = cursor.fetchone()
                assert row is not None
                self.assertEqual(int(row[0]), self.staging_count_before)

                cursor.execute(
                    """
                    SELECT action
                    FROM public.operator_audit_events
                    WHERE actor_user_id = %s
                    ORDER BY created_at, id
                    """,
                    (self.actor_id,),
                )
                actions = [row[0] for row in cursor.fetchall()]

        self.assertIn("source_created", actions)
        self.assertIn("source_updated", actions)
        self.assertIn("provider_source_binding_created", actions)
        self.assertIn("provider_source_binding_enabled", actions)
        self.assertIn("provider_source_binding_disabled", actions)


if __name__ == "__main__":
    unittest.main()
