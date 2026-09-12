import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from partgraph.errors import PartGraphError
from partgraph.identity.auth.models import User
from partgraph.operator import local_bootstrap
from partgraph.operator.models import OperatorAuditEvent


class FakeSession:
    def __init__(self, *, scalar_value=None) -> None:
        self.scalar_value = scalar_value
        self.added: list[object] = []
        self.executed = 0
        self.flushed = 0

    async def execute(self, *_args, **_kwargs):
        self.executed += 1
        return None

    async def scalar(self, *_args, **_kwargs):
        return self.scalar_value

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flushed += 1


def _local_environment() -> dict[str, str]:
    return {
        "PARTGRAPH_LOCAL_OPERATOR_BOOTSTRAP": "1",
        "PARTGRAPH_WEB_ORIGIN": "http://localhost:5173",
        "PARTGRAPH_DATABASE_URL": "postgresql+psycopg://partgraph:partgraph@postgres:5432/partgraph",
    }


def _user() -> User:
    return User(
        id=uuid4(),
        email="local@example.invalid",
        username="local_user",
        password_hash="unused-test-hash",
        role="owner",
        is_active=True,
    )


class LocalOperatorBootstrapTests(unittest.IsolatedAsyncioTestCase):
    def test_environment_gate_fails_closed(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(local_bootstrap.local_operator_bootstrap_environment())

        with patch.dict(
            os.environ,
            {**_local_environment(), "PARTGRAPH_WEB_ORIGIN": "https://example.com"},
            clear=True,
        ):
            self.assertFalse(local_bootstrap.local_operator_bootstrap_environment())

        with patch.dict(
            os.environ,
            {**_local_environment(), "PARTGRAPH_DATABASE_URL": "postgresql+psycopg://user:pass@remote.example/neondb"},
            clear=True,
        ):
            self.assertFalse(local_bootstrap.local_operator_bootstrap_environment())

        with patch.dict(
            os.environ,
            {**_local_environment(), "VERCEL": "1"},
            clear=True,
        ):
            self.assertFalse(local_bootstrap.local_operator_bootstrap_environment())

    def test_environment_gate_accepts_explicit_local_stack(self) -> None:
        with patch.dict(os.environ, _local_environment(), clear=True):
            self.assertTrue(local_bootstrap.local_operator_bootstrap_environment())

    async def test_bootstrap_is_unavailable_outside_local_stack(self) -> None:
        user = _user()
        session = FakeSession()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(PartGraphError) as raised:
                await local_bootstrap.bootstrap_local_operator(session, user=user)
        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(user.role, "owner")
        self.assertEqual(session.executed, 0)

    async def test_existing_operator_blocks_second_local_claim(self) -> None:
        user = _user()
        session = FakeSession(scalar_value=uuid4())
        with patch.dict(os.environ, _local_environment(), clear=True):
            with self.assertRaises(PartGraphError) as raised:
                await local_bootstrap.bootstrap_local_operator(session, user=user)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(user.role, "owner")
        self.assertEqual(session.flushed, 0)

    async def test_first_authenticated_local_user_claims_operator_and_is_audited(self) -> None:
        user = _user()
        session = FakeSession(scalar_value=None)
        with patch.dict(os.environ, _local_environment(), clear=True):
            await local_bootstrap.bootstrap_local_operator(session, user=user)

        self.assertEqual(user.role, "operator_admin")
        self.assertEqual(session.flushed, 1)
        self.assertEqual(len(session.added), 1)
        event = session.added[0]
        self.assertIsInstance(event, OperatorAuditEvent)
        self.assertEqual(event.action, "preview_operator_bootstrap")
        self.assertEqual(event.event_data, {"environment": "local"})
        self.assertEqual(event.actor_user_id, user.id)
        self.assertEqual(event.target_id, user.id)


if __name__ == "__main__":
    unittest.main()
