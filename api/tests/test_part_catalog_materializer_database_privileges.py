import os
import unittest

import psycopg

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
CURATOR_ROLE = "partgraph_curator"
MATERIALIZER_ROLE = "partgraph_materializer"


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


class PartCatalogMaterializerPrivilegeTests(unittest.TestCase):
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

    def test_materializer_can_append_part_catalog_but_cannot_mutate_it(self) -> None:
        for table in (
            "public.component_definitions",
            "public.part_identities",
            "public.component_part_roles",
        ):
            with self.subTest(table=table):
                self.assertTrue(
                    self._table_privilege(MATERIALIZER_ROLE, table, "SELECT")
                )
                self.assertTrue(
                    self._table_privilege(MATERIALIZER_ROLE, table, "INSERT")
                )
                self.assertFalse(
                    self._table_privilege(MATERIALIZER_ROLE, table, "UPDATE")
                )
                self.assertFalse(
                    self._table_privilege(MATERIALIZER_ROLE, table, "DELETE")
                )
                self.assertFalse(
                    self._table_privilege(CURATOR_ROLE, table, "INSERT")
                )


if __name__ == "__main__":
    unittest.main()
