import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy.exc import OperationalError
from starlette.requests import Request

from partgraph.errors import ErrorCode, PartGraphError
from partgraph.identity.auth.dependencies import _commit_auth_transaction
from partgraph.repair_experience.recovery import recover_session_mutation

IDEMPOTENCY_KEY = "rel004_same_key_1234"


def _request(
    *,
    method: str = "POST",
    path: str = "/api/v1/repair-sessions/00000000-0000-0000-0000-000000000001/pause",
    idempotency_key: str | None = IDEMPOTENCY_KEY,
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if idempotency_key is not None:
        headers.append((b"idempotency-key", idempotency_key.encode()))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "scheme": "https",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 12345),
            "server": ("partgraph.test", 443),
        }
    )


def _disconnect_error(*, invalidated: bool) -> OperationalError:
    return OperationalError(
        "COMMIT",
        {},
        RuntimeError("SSL connection has been closed unexpectedly"),
        connection_invalidated=invalidated,
    )


class _CommitThenDisconnect:
    def __init__(self, durable_store: dict[str, object], event: object) -> None:
        self.durable_store = durable_store
        self.event = event

    async def commit(self) -> None:
        # Simulate PostgreSQL durably committing before the acknowledgement path dies.
        self.durable_store[IDEMPOTENCY_KEY] = self.event
        raise _disconnect_error(invalidated=True)


class _CommitFailure:
    def __init__(self, *, invalidated: bool) -> None:
        self.invalidated = invalidated

    async def commit(self) -> None:
        raise _disconnect_error(invalidated=self.invalidated)


class _RecoveryDb:
    def __init__(self, session_id, event) -> None:
        self.session_id = session_id
        self.event = event
        self.calls = 0

    async def scalar(self, _statement):
        self.calls += 1
        return self.session_id if self.calls == 1 else self.event


class DatabaseWriteRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_post_commit_disconnect_surfaces_uncertain_write_then_recovers_same_key(self) -> None:
        durable_store: dict[str, object] = {}
        session_id = uuid4()
        user_id = uuid4()
        event = SimpleNamespace(
            event_type="session_paused",
            sequence=2,
            created_at=datetime.now(UTC),
        )
        transaction = _CommitThenDisconnect(durable_store, event)

        with self.assertRaises(PartGraphError) as captured:
            await _commit_auth_transaction(transaction, _request())  # type: ignore[arg-type]

        failure = captured.exception
        self.assertEqual(failure.code, ErrorCode.DATABASE_WRITE_STATE_UNCERTAIN)
        self.assertEqual(failure.status_code, 503)
        self.assertFalse(failure.retryable)
        self.assertEqual(failure.details["idempotency_key"], IDEMPOTENCY_KEY)
        self.assertTrue(failure.details["recovery_required"])
        self.assertIs(durable_store[IDEMPOTENCY_KEY], event)

        recovered = await recover_session_mutation(
            session_id=session_id,
            idempotency_key=IDEMPOTENCY_KEY,
            user=SimpleNamespace(id=user_id),  # type: ignore[arg-type]
            db=_RecoveryDb(session_id, durable_store[IDEMPOTENCY_KEY]),  # type: ignore[arg-type]
        )
        self.assertEqual(recovered.state, "committed")
        self.assertEqual(recovered.session_id, session_id)
        self.assertEqual(recovered.idempotency_key, IDEMPOTENCY_KEY)
        self.assertEqual(recovered.event_type, "session_paused")
        self.assertEqual(recovered.sequence, 2)

    async def test_non_disconnect_commit_failure_is_not_relabelled_uncertain(self) -> None:
        with self.assertRaises(OperationalError):
            await _commit_auth_transaction(
                _CommitFailure(invalidated=False),  # type: ignore[arg-type]
                _request(),
            )

    async def test_disconnect_without_recovery_key_is_not_declared_recoverable(self) -> None:
        with self.assertRaises(OperationalError):
            await _commit_auth_transaction(
                _CommitFailure(invalidated=True),  # type: ignore[arg-type]
                _request(idempotency_key=None),
            )

    async def test_disconnect_outside_repair_mutation_is_not_declared_recoverable(self) -> None:
        with self.assertRaises(OperationalError):
            await _commit_auth_transaction(
                _CommitFailure(invalidated=True),  # type: ignore[arg-type]
                _request(path="/api/v1/user-vehicles"),
            )


if __name__ == "__main__":
    unittest.main()
