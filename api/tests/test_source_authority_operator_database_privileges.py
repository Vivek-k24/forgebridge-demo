import inspect
import os
import unittest

import psycopg
from psycopg.errors import InsufficientPrivilege

from partgraph.operator import router as operator_router

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
APP_ROLE = "partgraph_app"
OPERATOR_ROLE = "partgraph_operator"


def _database_url() -> str:
    value = os.environ[DATABASE_URL_ENV]
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


class OperatorRouteDatabaseRoleTests(unittest.TestCase):
    def test_authorized_operator_routes_explicitly_assume_operator_database_role(self) -> None:
        routed_operations = (
            operator_router.users,
            operator_router.change_role,
            operator_router.providers,
            operator_router.add_provider,
            operator_router.change_provider,
            operator_router.sources,
            operator_router.add_source,
            operator_router.change_source,
            operator_router.provider_source_bindings,
            operator_router.add_provider_source_binding,
            operator_router.change_provider_source_binding,
            operator_router.stage_reference_parts,
            operator_router.stage_nhtsa_recalls,
            operator_router.audit,
        )
        for operation in routed_operations:
            with self.subTest(operation=operation.__name__):
                source = inspect.getsource(operation)
                self.assertIn("await assume_operator_database_role(session)", source)

    def test_bootstrap_mutation_transitions_only_after_authority_gate(self) -> None:
        source = inspect.getsource(operator_router.preview_bootstrap)
        self.assertIn("await assume_operator_database_role(session)", source)
        self.assertIn("if preview_operator_bootstrap_authorized(user):", source)
        self.assertLess(
            source.index("if preview_operator_bootstrap_authorized(user):"),
            source.rindex("await assume_operator_database_role(session)"),
        )


class OperatorDatabasePrivilegeTests(unittest.TestCase):
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

    def test_general_app_role_cannot_mutate_operator_configuration(self) -> None:
        for table in (
            "public.provider_connections",
            "public.provider_source_bindings",
            "public.catalog_sources",
            "public.operator_audit_events",
        ):
            for privilege in ("INSERT", "UPDATE", "DELETE"):
                with self.subTest(table=table, privilege=privilege):
                    self.assertFalse(self._table_privilege(APP_ROLE, table, privilege))

        self.assertFalse(self._table_privilege(APP_ROLE, "public.users", "UPDATE"))
        self.assertTrue(
            self._column_privilege(
                APP_ROLE,
                "public.users",
                "password_hash",
                "UPDATE",
            )
        )
        self.assertFalse(
            self._column_privilege(APP_ROLE, "public.users", "role", "UPDATE")
        )
        self._allowed(
            APP_ROLE,
            "UPDATE public.users SET password_hash = password_hash WHERE false",
        )
        self._denied(
            APP_ROLE,
            "UPDATE public.provider_connections SET enabled = enabled WHERE false",
        )

    def test_operator_role_has_only_required_configuration_write_privileges(self) -> None:
        for table in (
            "public.provider_connections",
            "public.provider_source_bindings",
            "public.catalog_sources",
        ):
            with self.subTest(table=table):
                self.assertTrue(self._table_privilege(OPERATOR_ROLE, table, "SELECT"))
                self.assertTrue(self._table_privilege(OPERATOR_ROLE, table, "INSERT"))
                self.assertTrue(self._table_privilege(OPERATOR_ROLE, table, "UPDATE"))
                self.assertFalse(self._table_privilege(OPERATOR_ROLE, table, "DELETE"))

        self.assertTrue(
            self._table_privilege(OPERATOR_ROLE, "public.operator_audit_events", "SELECT")
        )
        self.assertTrue(
            self._table_privilege(OPERATOR_ROLE, "public.operator_audit_events", "INSERT")
        )
        self.assertFalse(
            self._table_privilege(OPERATOR_ROLE, "public.operator_audit_events", "UPDATE")
        )
        self.assertFalse(
            self._table_privilege(OPERATOR_ROLE, "public.operator_audit_events", "DELETE")
        )
        self.assertTrue(self._table_privilege(OPERATOR_ROLE, "public.users", "SELECT"))
        self.assertTrue(
            self._column_privilege(OPERATOR_ROLE, "public.users", "role", "UPDATE")
        )
        self.assertFalse(
            self._column_privilege(
                OPERATOR_ROLE,
                "public.users",
                "password_hash",
                "UPDATE",
            )
        )

        for privilege in ("INSERT", "UPDATE", "DELETE"):
            with self.subTest(source_authority_privilege=privilege):
                self.assertFalse(
                    self._table_privilege(
                        OPERATOR_ROLE,
                        "public.source_authority_policies",
                        privilege,
                    )
                )

    def test_authenticated_transaction_can_explicitly_transition_to_operator_role(self) -> None:
        with self.connection.transaction():
            with self.connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {APP_ROLE}")
                cursor.execute(f"SET LOCAL ROLE {OPERATOR_ROLE}")
                cursor.execute("SELECT current_user")
                self.assertEqual(cursor.fetchone()[0], OPERATOR_ROLE)
                cursor.execute(
                    "UPDATE public.provider_connections SET enabled = enabled WHERE false"
                )
                cursor.execute(
                    "UPDATE public.provider_source_bindings SET enabled = enabled WHERE false"
                )
                cursor.execute(
                    "UPDATE public.catalog_sources SET display_name = display_name WHERE false"
                )
                cursor.execute("UPDATE public.users SET role = role WHERE false")
                cursor.execute(
                    """
                    INSERT INTO public.operator_audit_events
                        (id, actor_user_id, action, target_type, target_id)
                    SELECT id, id, 'provider_updated', 'user', id
                    FROM public.users
                    WHERE false
                    """
                )

    def test_operator_role_is_nologin_and_not_granted_to_app_role(self) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT rolcanlogin FROM pg_roles WHERE rolname = %s",
                (OPERATOR_ROLE,),
            )
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            assert row is not None
            self.assertFalse(row[0])
            cursor.execute(
                "SELECT pg_has_role(%s, %s, 'MEMBER')",
                (APP_ROLE, OPERATOR_ROLE),
            )
            self.assertFalse(cursor.fetchone()[0])


if __name__ == "__main__":
    unittest.main()
