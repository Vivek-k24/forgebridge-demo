import os
import unittest

import psycopg
from psycopg.errors import InsufficientPrivilege

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
APP_ROLE = "partgraph_app"
REVIEWER_ROLE = "partgraph_reviewer"


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


class DatabasePrivilegeBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")
        cls.connection = psycopg.connect(_database_url())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.connection.close()

    def _allowed(self, role: str, statement: str) -> None:
        with self.connection.transaction():
            with self.connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {role}")
                cursor.execute(statement)

    def _denied(self, role: str, statement: str) -> None:
        with self.assertRaises(InsufficientPrivilege):
            with self.connection.transaction():
                with self.connection.cursor() as cursor:
                    cursor.execute(f"SET LOCAL ROLE {role}")
                    cursor.execute(statement)

    def test_app_can_read_shared_vehicle_knowledge(self) -> None:
        self._allowed(APP_ROLE, "SELECT id FROM public.vehicle_configurations LIMIT 1")
        self._allowed(
            APP_ROLE,
            "SELECT id FROM public.vehicle_specification_profiles LIMIT 1",
        )
        self._allowed(
            APP_ROLE,
            "SELECT id FROM public.vehicle_structure_nodes LIMIT 1",
        )
        self._allowed(
            APP_ROLE,
            "SELECT id FROM public.component_definitions LIMIT 1",
        )
        self._allowed(APP_ROLE, "SELECT id FROM public.part_identities LIMIT 1")
        self._allowed(
            APP_ROLE,
            "SELECT id FROM public.component_part_roles LIMIT 1",
        )
        self._allowed(APP_ROLE, "SELECT id FROM public.part_fitments LIMIT 1")

    def test_app_cannot_read_internal_coverage_or_staging(self) -> None:
        self._denied(
            APP_ROLE,
            "SELECT id FROM public.catalog_coverage_batches LIMIT 1",
        )
        self._denied(
            APP_ROLE,
            "SELECT id FROM catalog_staging.source_records LIMIT 1",
        )

    def test_reviewer_transition_and_review_reads_work(self) -> None:
        with self.connection.transaction():
            with self.connection.cursor() as cursor:
                # Authenticated requests begin as partgraph_app before reviewer-only
                # endpoints narrow the same transaction to partgraph_reviewer.
                cursor.execute(f"SET LOCAL ROLE {APP_ROLE}")
                cursor.execute(f"SET LOCAL ROLE {REVIEWER_ROLE}")
                cursor.execute(
                    "SELECT id FROM public.catalog_coverage_batches LIMIT 1"
                )
                cursor.execute(
                    "SELECT id FROM public.catalog_coverage_items LIMIT 1"
                )
                cursor.execute(
                    "SELECT id FROM catalog_staging.source_records LIMIT 1"
                )
                cursor.execute(
                    "SELECT id FROM public.vehicle_configurations LIMIT 1"
                )
                cursor.execute(
                    "SELECT id FROM public.vehicle_structure_nodes LIMIT 1"
                )
                cursor.execute(
                    "SELECT id FROM public.component_definitions LIMIT 1"
                )
                cursor.execute("SELECT id FROM public.part_identities LIMIT 1")
                cursor.execute(
                    "SELECT id FROM public.component_part_roles LIMIT 1"
                )
                cursor.execute("SELECT id FROM public.part_fitments LIMIT 1")

    def test_reviewer_cannot_mutate_coverage_or_canonical_truth(self) -> None:
        self._denied(
            REVIEWER_ROLE,
            "UPDATE public.catalog_coverage_batches SET label = label WHERE false",
        )
        self._denied(
            REVIEWER_ROLE,
            "DELETE FROM public.catalog_coverage_items WHERE false",
        )
        self._denied(
            REVIEWER_ROLE,
            "UPDATE public.vehicle_configurations SET make = make WHERE false",
        )
        self._denied(
            REVIEWER_ROLE,
            "UPDATE public.vehicle_structure_nodes SET display_name = display_name WHERE false",
        )
        self._denied(
            REVIEWER_ROLE,
            "UPDATE public.component_definitions SET display_name = display_name WHERE false",
        )
        self._denied(
            REVIEWER_ROLE,
            "UPDATE public.part_identities SET display_name = display_name WHERE false",
        )
        self._denied(
            REVIEWER_ROLE,
            "DELETE FROM public.component_part_roles WHERE false",
        )
        self._denied(
            REVIEWER_ROLE,
            "UPDATE public.part_fitments SET applicability_state = applicability_state WHERE false",
        )


if __name__ == "__main__":
    unittest.main()
