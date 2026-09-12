import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from partgraph.errors import PartGraphError
from partgraph.identity.auth.models import User
from partgraph.operator import service
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


def _preview_environment() -> dict[str, str]:
    return {
        "VERCEL": "1",
        "VERCEL_ENV": "preview",
        "VERCEL_GIT_COMMIT_REF": "partgraph-mvp-consolidation",
    }


def _user() -> User:
    return User(
        id=uuid4(),
        email="preview@example.invalid",
        username="preview_user",
        password_hash="unused-test-hash",
        role="owner",
        is_active=True,
    )


class PreviewOperatorBootstrapTests(unittest.IsolatedAsyncioTestCase):
    def test_environment_gate_fails_closed(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(service._preview_bootstrap_environment())

        with patch.dict(
            os.environ,
            {**_preview_environment(), "VERCEL_ENV": "production"},
            clear=True,
        ):
            self.assertFalse(service._preview_bootstrap_environment())

        with patch.dict(
            os.environ,
            {**_preview_environment(), "VERCEL_GIT_COMMIT_REF": "main"},
            clear=True,
        ):
            self.assertFalse(service._preview_bootstrap_environment())

    def test_environment_gate_accepts_only_target_preview(self) -> None:
        with patch.dict(os.environ, _preview_environment(), clear=True):
            self.assertTrue(service._preview_bootstrap_environment())

    async def test_bootstrap_is_unavailable_outside_target_preview(self) -> None:
        user = _user()
        session = FakeSession()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(PartGraphError) as raised:
                await service.bootstrap_preview_operator(session, user=user)
        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(user.role, "owner")
        self.assertEqual(session.executed, 0)

    async def test_existing_operator_blocks_second_claim(self) -> None:
        user = _user()
        session = FakeSession(scalar_value=uuid4())
        with patch.dict(os.environ, _preview_environment(), clear=True):
            with self.assertRaises(PartGraphError) as raised:
                await service.bootstrap_preview_operator(session, user=user)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(user.role, "owner")
        self.assertEqual(session.flushed, 0)

    async def test_first_authenticated_preview_user_claims_operator_and_is_audited(self) -> None:
        user = _user()
        session = FakeSession(scalar_value=None)
        with patch.dict(os.environ, _preview_environment(), clear=True):
            await service.bootstrap_preview_operator(session, user=user)

        self.assertEqual(user.role, "operator_admin")
        self.assertEqual(session.flushed, 1)
        self.assertEqual(len(session.added), 1)
        event = session.added[0]
        self.assertIsInstance(event, OperatorAuditEvent)
        self.assertEqual(event.action, "preview_operator_bootstrap")
        self.assertEqual(event.actor_user_id, user.id)
        self.assertEqual(event.target_id, user.id)


if __name__ == "__main__":
    unittest.main()
