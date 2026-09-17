import os
import unittest
from uuid import uuid4

import psycopg
from psycopg.errors import InsufficientPrivilege

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
APP_ROLE = "partgraph_app"
OWNER_CONTEXT = "partgraph.user_id"
OWNER_RLS_EXEMPT_APP_USER_TABLES = {"auth_sessions"}
REQUIRED_OWNER_TABLES = {
    "owner_equipment_items",
    "repair_photo_evidence",
    "repair_sessions",
    "user_preferences",
    "user_vehicles",
}


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


class FinalMvpOwnerIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")
        cls.connection = psycopg.connect(_database_url())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.connection.close()

    def setUp(self) -> None:
        self.owner_a = uuid4()
        self.owner_b = uuid4()
        self.owner_c = uuid4()
        self._seed_user(self.owner_a, "owner_a")
        self._seed_user(self.owner_b, "owner_b")
        self._seed_user(self.owner_c, "owner_c")
        with self.connection.transaction():
            with self.connection.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO public.user_preferences (user_id, units) VALUES (%s, %s)",
                    [
                        (self.owner_a, "us_customary"),
                        (self.owner_b, "metric"),
                    ],
                )

    def tearDown(self) -> None:
        with self.connection.transaction():
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM public.users WHERE id = ANY(%s)",
                    ([self.owner_a, self.owner_b, self.owner_c],),
                )

    def _seed_user(self, user_id, prefix: str) -> None:
        suffix = uuid4().hex[:12]
        username = f"{prefix}_{suffix}"
        with self.connection.transaction():
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.users (id, email, username, password_hash)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        f"{username}@example.com",
                        username,
                        "$argon2id$v=19$m=65536,t=3,p=4$phase9$ownerisolation",
                    ),
                )

    def _visible_preference_owners(self, owner_id=None) -> set[str]:
        with self.connection.transaction():
            with self.connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {APP_ROLE}")
                if owner_id is not None:
                    cursor.execute(
                        "SELECT set_config(%s, %s, true)",
                        (OWNER_CONTEXT, str(owner_id)),
                    )
                cursor.execute(
                    "SELECT user_id::text FROM public.user_preferences ORDER BY user_id"
                )
                return {row[0] for row in cursor.fetchall()}

    def test_all_app_accessible_user_owned_tables_force_owner_rls(self) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.relname
                FROM pg_catalog.pg_class AS c
                JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
                JOIN information_schema.columns AS col
                  ON col.table_schema = n.nspname
                 AND col.table_name = c.relname
                WHERE n.nspname = 'public'
                  AND c.relkind = 'r'
                  AND col.column_name = 'user_id'
                  AND has_table_privilege(%s, format('%I.%I', n.nspname, c.relname), 'SELECT')
                ORDER BY c.relname
                """,
                (APP_ROLE,),
            )
            app_user_tables = {row[0] for row in cursor.fetchall()}

        owner_tables = app_user_tables - OWNER_RLS_EXEMPT_APP_USER_TABLES
        self.assertTrue(REQUIRED_OWNER_TABLES.issubset(owner_tables), owner_tables)
        self.assertEqual(
            app_user_tables & OWNER_RLS_EXEMPT_APP_USER_TABLES,
            OWNER_RLS_EXEMPT_APP_USER_TABLES,
        )

        with self.connection.cursor() as cursor:
            for table in sorted(owner_tables):
                with self.subTest(table=table):
                    cursor.execute(
                        """
                        SELECT relrowsecurity, relforcerowsecurity
                        FROM pg_catalog.pg_class
                        WHERE oid = %s::regclass
                        """,
                        (f"public.{table}",),
                    )
                    row = cursor.fetchone()
                    self.assertEqual(row, (True, True))

                    cursor.execute(
                        """
                        SELECT qual, with_check
                        FROM pg_catalog.pg_policies
                        WHERE schemaname = 'public'
                          AND tablename = %s
                          AND policyname = %s
                        """,
                        (table, f"{table}_owner"),
                    )
                    policy = cursor.fetchone()
                    self.assertIsNotNone(policy, table)
                    assert policy is not None
                    self.assertIn(OWNER_CONTEXT, policy[0] or "")
                    self.assertIn(OWNER_CONTEXT, policy[1] or "")

    def test_owner_context_filters_private_rows_and_no_context_fails_closed(self) -> None:
        self.assertEqual(self._visible_preference_owners(), set())
        self.assertEqual(
            self._visible_preference_owners(self.owner_a),
            {str(self.owner_a)},
        )
        self.assertEqual(
            self._visible_preference_owners(self.owner_b),
            {str(self.owner_b)},
        )

    def test_owner_context_is_transaction_local_and_does_not_leak(self) -> None:
        self.assertEqual(
            self._visible_preference_owners(self.owner_a),
            {str(self.owner_a)},
        )
        self.assertEqual(self._visible_preference_owners(), set())

    def test_owner_can_update_own_row_but_not_another_owners_row(self) -> None:
        with self.connection.transaction():
            with self.connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {APP_ROLE}")
                cursor.execute(
                    "SELECT set_config(%s, %s, true)",
                    (OWNER_CONTEXT, str(self.owner_a)),
                )
                cursor.execute(
                    "UPDATE public.user_preferences SET units = 'metric' WHERE user_id = %s",
                    (self.owner_a,),
                )
                self.assertEqual(cursor.rowcount, 1)
                cursor.execute(
                    "UPDATE public.user_preferences SET units = 'us_customary' WHERE user_id = %s",
                    (self.owner_b,),
                )
                self.assertEqual(cursor.rowcount, 0)

        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT units FROM public.user_preferences WHERE user_id = %s",
                (self.owner_b,),
            )
            self.assertEqual(cursor.fetchone()[0], "metric")

    def test_with_check_rejects_cross_owner_inserts(self) -> None:
        with self.assertRaises(InsufficientPrivilege):
            with self.connection.transaction():
                with self.connection.cursor() as cursor:
                    cursor.execute(f"SET LOCAL ROLE {APP_ROLE}")
                    cursor.execute(
                        "SELECT set_config(%s, %s, true)",
                        (OWNER_CONTEXT, str(self.owner_a)),
                    )
                    cursor.execute(
                        "INSERT INTO public.user_preferences (user_id, units) VALUES (%s, %s)",
                        (self.owner_c, "metric"),
                    )

        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM public.user_preferences WHERE user_id = %s",
                (self.owner_c,),
            )
            self.assertEqual(cursor.fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
