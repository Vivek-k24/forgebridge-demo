import os
import unittest

import psycopg

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
APP_ROLE = "partgraph_app"
CURATOR_ROLE = "partgraph_curator"
MATERIALIZER_ROLE = "partgraph_materializer"
TABLES = (
    "public.procedure_action_milestones",
    "public.repair_downstream_requirements",
    "public.repair_downstream_requirement_evidence",
)


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


class DownstreamMaterializerPrivilegeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")
        cls.connection = psycopg.connect(_database_url())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.connection.close()

    def _privilege(self, role: str, table: str, privilege: str) -> bool:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT has_table_privilege(%s, %s, %s)",
                (role, table, privilege),
            )
            row = cursor.fetchone()
            assert row is not None
            return bool(row[0])

    def test_materializer_has_append_only_downstream_authority(self) -> None:
        for table in TABLES:
            with self.subTest(table=table):
                self.assertTrue(self._privilege(MATERIALIZER_ROLE, table, "SELECT"))
                self.assertTrue(self._privilege(MATERIALIZER_ROLE, table, "INSERT"))
                self.assertFalse(self._privilege(MATERIALIZER_ROLE, table, "UPDATE"))
                self.assertFalse(self._privilege(MATERIALIZER_ROLE, table, "DELETE"))

    def test_curator_and_app_cannot_write_canonical_downstream_truth(self) -> None:
        for role in (CURATOR_ROLE, APP_ROLE):
            for table in TABLES:
                for privilege in ("INSERT", "UPDATE", "DELETE"):
                    with self.subTest(role=role, table=table, privilege=privilege):
                        self.assertFalse(self._privilege(role, table, privilege))


if __name__ == "__main__":
    unittest.main()
