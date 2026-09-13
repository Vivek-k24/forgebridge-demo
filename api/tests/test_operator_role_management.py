import unittest
from datetime import UTC, datetime
from uuid import uuid4

from partgraph.errors import ErrorCode, PartGraphError
from partgraph.identity.auth.models import User
from partgraph.operator import service
from partgraph.operator.models import OperatorAuditEvent
from partgraph.operator.schemas import UserRoleUpdate


class _Result:
    def __init__(self, value) -> None:
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeSession:
    def __init__(self, *, target: User | None, active_operator_ids=None) -> None:
        self.target = target
        self.active_operator_ids = list(active_operator_ids or [])
        self.execute_calls = 0
        self.added: list[object] = []
        self.flushed = 0

    async def execute(self, *_args, **_kwargs):
        self.execute_calls += 1
        if self.execute_calls == 1:
            return None
        return _Result(self.target)

    async def scalars(self, *_args, **_kwargs):
        return self.active_operator_ids

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flushed += 1


def _user(*, role: str = "owner") -> User:
    return User(
        id=uuid4(),
        email=f"{uuid4().hex}@example.invalid",
        username=f"user_{uuid4().hex[:8]}",
        password_hash="unused-test-hash",
        role=role,
        is_active=True,
        created_at=datetime.now(UTC),
    )


class OperatorRoleManagementTests(unittest.IsolatedAsyncioTestCase):
    async def test_role_change_is_audited(self) -> None:
        actor = _user(role="operator_admin")
        target = _user(role="owner")
        session = FakeSession(target=target)

        result = await service.change_user_role(
            session,
            actor_id=actor.id,
            target_user_id=target.id,
            payload=UserRoleUpdate(role="reviewer"),
        )

        self.assertEqual(target.role, "reviewer")
        self.assertEqual(result.role, "reviewer")
        self.assertEqual(session.flushed, 1)
        self.assertEqual(len(session.added), 1)
        event = session.added[0]
        self.assertIsInstance(event, OperatorAuditEvent)
        self.assertEqual(event.action, "user_role_changed")
        self.assertEqual(event.actor_user_id, actor.id)
        self.assertEqual(event.target_id, target.id)
        self.assertEqual(event.event_data["previous_role"], "owner")
        self.assertEqual(event.event_data["new_role"], "reviewer")

    async def test_last_active_operator_cannot_be_demoted(self) -> None:
        target = _user(role="operator_admin")
        session = FakeSession(target=target, active_operator_ids=[target.id])

        with self.assertRaises(PartGraphError) as raised:
            await service.change_user_role(
                session,
                actor_id=target.id,
                target_user_id=target.id,
                payload=UserRoleUpdate(role="owner"),
            )

        self.assertEqual(raised.exception.code, ErrorCode.OPERATOR_LAST_ADMIN_REQUIRED)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(target.role, "operator_admin")
        self.assertEqual(session.flushed, 0)
        self.assertEqual(session.added, [])

    async def test_missing_target_is_not_found(self) -> None:
        actor = _user(role="operator_admin")
        session = FakeSession(target=None)

        with self.assertRaises(PartGraphError) as raised:
            await service.change_user_role(
                session,
                actor_id=actor.id,
                target_user_id=uuid4(),
                payload=UserRoleUpdate(role="reviewer"),
            )

        self.assertEqual(raised.exception.code, ErrorCode.OPERATOR_USER_NOT_FOUND)
        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(session.flushed, 0)


if __name__ == "__main__":
    unittest.main()
