import os
import unittest

import psycopg

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
APP_ROLE = "partgraph_app"
REVIEWER_ROLE = "partgraph_reviewer"
CONTRIBUTOR_ROLE = "partgraph_contributor"
CURATOR_ROLE = "partgraph_curator"


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


class PipelineDatabasePrivilegeTests(unittest.TestCase):
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

    def _column_privilege(
        self,
        role: str,
        table: str,
        column: str,
        privilege: str,
    ) -> bool:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT has_column_privilege(%s, %s, %s, %s)",
                (role, table, column, privilege),
            )
            row = cursor.fetchone()
            assert row is not None
            return bool(row[0])

    def test_authenticated_transaction_can_narrow_to_pipeline_roles(self) -> None:
        with self.connection.transaction():
            with self.connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {APP_ROLE}")
                cursor.execute(f"SET LOCAL ROLE {CONTRIBUTOR_ROLE}")
                cursor.execute("SELECT current_user")
                self.assertEqual(cursor.fetchone()[0], CONTRIBUTOR_ROLE)

        with self.connection.transaction():
            with self.connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {APP_ROLE}")
                cursor.execute(f"SET LOCAL ROLE {CURATOR_ROLE}")
                cursor.execute("SELECT current_user")
                self.assertEqual(cursor.fetchone()[0], CURATOR_ROLE)

    def test_contributor_is_staging_write_only(self) -> None:
        self.assertTrue(
            self._table_privilege(CONTRIBUTOR_ROLE, "public.catalog_sources", "SELECT")
        )
        self.assertTrue(
            self._table_privilege(CONTRIBUTOR_ROLE, "public.vehicle_configurations", "SELECT")
        )
        self.assertTrue(
            self._table_privilege(
                CONTRIBUTOR_ROLE,
                "catalog_staging.ingestion_batches",
                "INSERT",
            )
        )
        self.assertTrue(
            self._table_privilege(
                CONTRIBUTOR_ROLE,
                "catalog_staging.source_records",
                "INSERT",
            )
        )
        self.assertFalse(
            self._table_privilege(
                CONTRIBUTOR_ROLE,
                "catalog_staging.source_records",
                "SELECT",
            )
        )
        self.assertFalse(
            self._table_privilege(
                CONTRIBUTOR_ROLE,
                "public.catalog_verified_evidence",
                "INSERT",
            )
        )
        self.assertFalse(
            self._table_privilege(
                CONTRIBUTOR_ROLE,
                "public.mechanical_claims",
                "INSERT",
            )
        )
        self.assertFalse(
            self._table_privilege(
                CONTRIBUTOR_ROLE,
                "public.part_fitments",
                "INSERT",
            )
        )

    def test_reviewer_still_stops_at_verified_evidence(self) -> None:
        self.assertTrue(
            self._table_privilege(
                REVIEWER_ROLE,
                "public.catalog_verified_evidence",
                "INSERT",
            )
        )
        self.assertFalse(
            self._table_privilege(REVIEWER_ROLE, "public.mechanical_claims", "INSERT")
        )
        self.assertFalse(
            self._table_privilege(REVIEWER_ROLE, "public.canonical_conflicts", "INSERT")
        )

    def test_curator_can_publish_claims_and_quarantine_conflicts_only(self) -> None:
        self.assertTrue(
            self._table_privilege(
                CURATOR_ROLE,
                "public.catalog_verified_evidence",
                "SELECT",
            )
        )
        self.assertTrue(
            self._table_privilege(CURATOR_ROLE, "public.mechanical_claims", "INSERT")
        )
        self.assertTrue(
            self._column_privilege(
                CURATOR_ROLE,
                "public.mechanical_claims",
                "promotion_state",
                "UPDATE",
            )
        )
        self.assertTrue(
            self._column_privilege(
                CURATOR_ROLE,
                "public.mechanical_claims",
                "reviewed_at",
                "UPDATE",
            )
        )
        self.assertTrue(
            self._table_privilege(CURATOR_ROLE, "public.canonical_conflicts", "INSERT")
        )
        self.assertTrue(
            self._table_privilege(
                CURATOR_ROLE,
                "public.canonical_conflict_items",
                "INSERT",
            )
        )

        for table in (
            "public.vehicle_configurations",
            "public.part_identities",
            "public.part_fitments",
            "public.requirement_definitions",
            "public.repair_definitions",
            "public.repair_operations",
            "public.procedure_actions",
            "public.material_definitions",
            "public.specification_definitions",
        ):
            with self.subTest(table=table):
                self.assertFalse(self._table_privilege(CURATOR_ROLE, table, "INSERT"))
                self.assertFalse(self._table_privilege(CURATOR_ROLE, table, "DELETE"))

        self.assertFalse(
            self._table_privilege(
                CURATOR_ROLE,
                "public.canonical_record_versions",
                "INSERT",
            )
        )
        self.assertFalse(
            self._table_privilege(
                CURATOR_ROLE,
                "public.catalog_verified_evidence",
                "UPDATE",
            )
        )


if __name__ == "__main__":
    unittest.main()
