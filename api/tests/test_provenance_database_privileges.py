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


class ProvenanceDatabasePrivilegeTests(unittest.TestCase):
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

    def test_app_and_reviewer_can_read_publication_provenance(self) -> None:
        for role in (APP_ROLE, REVIEWER_ROLE):
            self._allowed(role, "SELECT id FROM public.canonical_record_versions LIMIT 1")
            self._allowed(role, "SELECT id FROM public.canonical_record_evidence LIMIT 1")
            self._allowed(role, "SELECT id FROM public.canonical_conflicts LIMIT 1")
            self._allowed(role, "SELECT id FROM public.canonical_conflict_items LIMIT 1")

    def test_app_and_reviewer_cannot_mutate_publication_provenance(self) -> None:
        for role in (APP_ROLE, REVIEWER_ROLE):
            self._denied(
                role,
                "UPDATE public.canonical_record_versions "
                "SET publication_state = publication_state WHERE false",
            )
            self._denied(
                role,
                "DELETE FROM public.canonical_record_evidence WHERE false",
            )
            self._denied(
                role,
                "UPDATE public.canonical_conflicts "
                "SET conflict_state = conflict_state WHERE false",
            )
            self._denied(
                role,
                "DELETE FROM public.canonical_conflict_items WHERE false",
            )


if __name__ == "__main__":
    unittest.main()
