import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from partgraph.errors import PartGraphError
from partgraph.identity.auth.models import User
from partgraph.operator import preview_bootstrap, service
from partgraph.operator import router as operator_router
from partgraph.operator.models import OperatorAuditEvent


class FakeSession:
    def __init__(self, *, scalar_value=None) -> None:
        self.scalar_value = scalar_value
        self.added: list[object] = []
        self.executed = 0
        self.scalar_calls = 0
        self.flushed = 0

    async def execute(self, *_args, **_kwargs):
        self.executed += 1
        return None

    async def scalar(self, *_args, **_kwargs):
        self.scalar_calls += 1
        return self.scalar_value

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flushed += 1


def _preview_environment(*, authorized_user_id=None) -> dict[str, str]:
    environment = {
        "VERCEL": "1",
        "VERCEL_ENV": "preview",
        "VERCEL_GIT_COMMIT_REF": "partgraph-mvp-consolidation",
    }
    if authorized_user_id is not None:
        environment[preview_bootstrap.PREVIEW_OPERATOR_BOOTSTRAP_USER_ID_ENV] = str(
            authorized_user_id
        )
    return environment


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

    def test_router_uses_authorized_preview_bootstrap_wrapper(self) -> None:
        self.assertIs(
            operator_router.bootstrap_preview_operator,
            preview_bootstrap.bootstrap_preview_operator,
        )
        self.assertIs(
            operator_router.preview_operator_bootstrap_status,
            preview_bootstrap.preview_operator_bootstrap_status,
        )

    def test_missing_or_invalid_authority_fails_closed(self) -> None:
        user = _user()
        with patch.dict(os.environ, _preview_environment(), clear=True):
            self.assertIsNone(
                preview_bootstrap.configured_preview_operator_bootstrap_user_id()
            )
            self.assertFalse(preview_bootstrap.preview_operator_bootstrap_authorized(user))

        with patch.dict(
            os.environ,
            {
                **_preview_environment(),
                preview_bootstrap.PREVIEW_OPERATOR_BOOTSTRAP_USER_ID_ENV: "not-a-uuid",
            },
            clear=True,
        ):
            self.assertIsNone(
                preview_bootstrap.configured_preview_operator_bootstrap_user_id()
            )
            self.assertFalse(preview_bootstrap.preview_operator_bootstrap_authorized(user))

    async def test_arbitrary_authenticated_user_cannot_claim_operator(self) -> None:
        user = _user()
        authorized_user_id = uuid4()
        session = FakeSession()
        with patch.dict(
            os.environ,
            _preview_environment(authorized_user_id=authorized_user_id),
            clear=True,
        ):
            with self.assertRaises(PartGraphError) as raised:
                await preview_bootstrap.bootstrap_preview_operator(session, user=user)

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(user.role, "owner")
        self.assertEqual(session.executed, 0)
        self.assertEqual(session.scalar_calls, 0)
        self.assertEqual(session.flushed, 0)

    async def test_unauthorized_status_is_unavailable_without_database_lookup(self) -> None:
        user = _user()
        session = FakeSession()
        with patch.dict(
            os.environ,
            _preview_environment(authorized_user_id=uuid4()),
            clear=True,
        ):
            status = await preview_bootstrap.preview_operator_bootstrap_status(
                session,
                user=user,
            )

        self.assertFalse(status.available)
        self.assertEqual(session.scalar_calls, 0)

    async def test_authorized_user_can_claim_once_and_is_audited(self) -> None:
        user = _user()
        session = FakeSession(scalar_value=None)
        with patch.dict(
            os.environ,
            _preview_environment(authorized_user_id=user.id),
            clear=True,
        ):
            status = await preview_bootstrap.preview_operator_bootstrap_status(
                session,
                user=user,
            )
            self.assertTrue(status.available)
            await preview_bootstrap.bootstrap_preview_operator(session, user=user)

        self.assertEqual(user.role, "operator_admin")
        self.assertEqual(session.executed, 1)
        self.assertEqual(session.flushed, 1)
        self.assertEqual(len(session.added), 1)
        event = session.added[0]
        self.assertIsInstance(event, OperatorAuditEvent)
        self.assertEqual(event.action, "preview_operator_bootstrap")
        self.assertEqual(event.actor_user_id, user.id)
        self.assertEqual(event.target_id, user.id)
        self.assertEqual(event.event_data["environment"], "preview")

    async def test_existing_operator_blocks_authorized_user(self) -> None:
        user = _user()
        session = FakeSession(scalar_value=uuid4())
        with patch.dict(
            os.environ,
            _preview_environment(authorized_user_id=user.id),
            clear=True,
        ):
            with self.assertRaises(PartGraphError) as raised:
                await preview_bootstrap.bootstrap_preview_operator(session, user=user)

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(user.role, "owner")
        self.assertEqual(session.flushed, 0)


if __name__ == "__main__":
    unittest.main()
