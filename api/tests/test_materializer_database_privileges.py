import os
import unittest

import psycopg

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
APP_ROLE = "partgraph_app"
CURATOR_ROLE = "partgraph_curator"
MATERIALIZER_ROLE = "partgraph_materializer"


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


class MaterializerDatabasePrivilegeTests(unittest.TestCase):
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

    def test_app_transaction_can_narrow_to_materializer(self) -> None:
        with self.connection.transaction():
            with self.connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {APP_ROLE}")
                cursor.execute(f"SET LOCAL ROLE {MATERIALIZER_ROLE}")
                cursor.execute("SELECT current_user")
                self.assertEqual(cursor.fetchone()[0], MATERIALIZER_ROLE)

    def test_curator_role_itself_remains_noncanonical_writer(self) -> None:
        self.assertFalse(
            self._table_privilege(CURATOR_ROLE, "public.repair_definitions", "INSERT")
        )
        self.assertFalse(
            self._table_privilege(
                CURATOR_ROLE,
                "public.canonical_record_versions",
                "INSERT",
            )
        )
        self.assertFalse(
            self._table_privilege(CURATOR_ROLE, "public.part_fitments", "INSERT")
        )
        self.assertFalse(
            self._column_privilege(
                CURATOR_ROLE,
                "public.vehicle_configurations",
                "verification_status",
                "UPDATE",
            )
        )

    def test_materializer_reads_claim_scope_but_cannot_create_claims(self) -> None:
        for table in (
            "public.catalog_sources",
            "public.vehicle_configurations",
            "public.mechanical_claims",
            "public.canonical_conflicts",
            "public.repair_capability_policies",
            "public.source_authority_policies",
            "public.component_part_roles",
            "public.part_fitments",
        ):
            with self.subTest(table=table):
                self.assertTrue(self._table_privilege(MATERIALIZER_ROLE, table, "SELECT"))
        self.assertFalse(
            self._table_privilege(MATERIALIZER_ROLE, "public.mechanical_claims", "INSERT")
        )
        self.assertFalse(
            self._column_privilege(
                MATERIALIZER_ROLE,
                "public.mechanical_claims",
                "claim_payload",
                "UPDATE",
            )
        )

    def test_materializer_has_narrow_vehicle_and_fitment_writes(self) -> None:
        self.assertTrue(
            self._column_privilege(
                MATERIALIZER_ROLE,
                "public.vehicle_configurations",
                "verification_status",
                "UPDATE",
            )
        )
        for column in ("make", "model", "trim", "engine", "identity_hash"):
            with self.subTest(column=column):
                self.assertFalse(
                    self._column_privilege(
                        MATERIALIZER_ROLE,
                        "public.vehicle_configurations",
                        column,
                        "UPDATE",
                    )
                )

        self.assertTrue(
            self._table_privilege(MATERIALIZER_ROLE, "public.part_fitments", "INSERT")
        )
        self.assertFalse(
            self._table_privilege(MATERIALIZER_ROLE, "public.part_fitments", "UPDATE")
        )
        self.assertFalse(
            self._table_privilege(MATERIALIZER_ROLE, "public.part_fitments", "DELETE")
        )
        self.assertFalse(
            self._table_privilege(
                MATERIALIZER_ROLE,
                "public.component_part_roles",
                "INSERT",
            )
        )

    def test_materializer_can_append_only_repair_publication_graph(self) -> None:
        tables = (
            "public.repair_definitions",
            "public.repair_operations",
            "public.requirement_definitions",
            "public.requirement_uses",
            "public.requirement_use_evidence",
            "public.procedure_actions",
            "public.procedure_action_dependencies",
            "public.procedure_action_requirement_uses",
            "public.procedure_action_evidence",
            "public.canonical_record_versions",
            "public.canonical_record_evidence",
        )
        for table in tables:
            with self.subTest(table=table):
                self.assertTrue(self._table_privilege(MATERIALIZER_ROLE, table, "SELECT"))
                self.assertTrue(self._table_privilege(MATERIALIZER_ROLE, table, "INSERT"))
                self.assertFalse(self._table_privilege(MATERIALIZER_ROLE, table, "DELETE"))

        for column in ("status", "superseded_by_id"):
            self.assertTrue(
                self._column_privilege(
                    MATERIALIZER_ROLE,
                    "public.repair_definitions",
                    column,
                    "UPDATE",
                )
            )
        self.assertTrue(
            self._column_privilege(
                MATERIALIZER_ROLE,
                "public.canonical_record_versions",
                "publication_state",
                "UPDATE",
            )
        )

        for table, column in (
            ("public.repair_definitions", "title"),
            ("public.requirement_definitions", "display_name"),
            ("public.procedure_actions", "instruction"),
            ("public.canonical_record_versions", "record_id"),
            ("public.canonical_record_evidence", "evidence_role"),
        ):
            with self.subTest(table=table, column=column):
                self.assertFalse(
                    self._column_privilege(
                        MATERIALIZER_ROLE,
                        table,
                        column,
                        "UPDATE",
                    )
                )


if __name__ == "__main__":
    unittest.main()
