import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import DBAPIError

from partgraph.auth.service import set_user_context
from partgraph.database import session_factory
from partgraph.main import app
from partgraph.repair_session.models import (
    RepairSessionEvent,
    RepairSessionProjection,
)

CSRF = {"X-PartGraph-CSRF": "1"}
PASSWORD = "correct-horse-battery-staple"


def _register(client: TestClient, prefix: str) -> str:
    suffix = uuid4().hex[:12]
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"{prefix}-{suffix}@example.com",
            "username": f"{prefix}_{suffix}"[:32],
            "password": PASSWORD,
        },
        headers=CSRF,
    )
    assert response.status_code == 200, response.text
    return response.json()["user"]["id"]


def _error_code(response) -> str:
    payload = response.json()
    assert set(payload) == {"error"}
    assert isinstance(payload["error"]["request_id"], str)
    return str(payload["error"]["code"])


def _create_vehicle(client: TestClient, prefix: str = "RepairModel") -> str:
    response = client.post(
        "/api/v1/user-vehicles/manual",
        json={
            "nickname": "Project car",
            "selection": {
                "year": 2009,
                "market": "US",
                "make": "Honda",
                "model": f"{prefix}-{uuid4().hex[:8]}",
                "trim": "EX",
            },
        },
        headers=CSRF,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _session_headers(device_id: str, idempotency_key: str | None = None) -> dict[str, str]:
    headers = {**CSRF, "X-PartGraph-Device-ID": device_id}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def _create_session(
    client: TestClient,
    *,
    vehicle_id: str,
    device_id: str,
    key: str = "create_session_01",
    title: str = "Front-end repair",
):
    return client.post(
        "/api/v1/repair-sessions",
        json={"user_vehicle_id": vehicle_id, "title": title},
        headers=_session_headers(device_id, key),
    )


def _copy_auth(source: TestClient, target: TestClient) -> None:
    token = source.cookies.get("partgraph_session")
    assert token
    target.cookies.set("partgraph_session", token)


def test_repair_session_lifecycle_idempotency_lease_and_archive() -> None:
    device_a = str(uuid4())
    device_b = str(uuid4())

    with TestClient(app) as owner:
        _register(owner, "repair_owner")
        vehicle_id = _create_vehicle(owner)
        created = _create_session(owner, vehicle_id=vehicle_id, device_id=device_a)
        assert created.status_code == 201, created.text
        first = created.json()
        session_id = first["session"]["id"]
        assert first["session"]["status"] == "active"
        assert first["session"]["current_sequence"] == 1
        assert first["last_event"]["event_type"] == "session_started"
        assert first["lease"]["status"] == "owned"
        assert first["lease"]["can_edit"] is True
        assert created.headers["cache-control"] == "no-store"

        repeated = _create_session(owner, vehicle_id=vehicle_id, device_id=device_a)
        assert repeated.status_code == 201, repeated.text
        assert repeated.json()["session"]["id"] == session_id

        conflict = _create_session(
            owner,
            vehicle_id=vehicle_id,
            device_id=device_a,
            title="Different repair",
        )
        assert conflict.status_code == 409
        assert _error_code(conflict) == "REPAIR_SESSION_IDEMPOTENCY_CONFLICT"

        viewer = owner.get(
            f"/api/v1/repair-sessions/{session_id}/resume",
            headers={"X-PartGraph-Device-ID": device_b},
        )
        assert viewer.status_code == 200
        assert viewer.json()["lease"]["status"] == "held_by_other"
        assert viewer.json()["lease"]["can_edit"] is False

        blocked = owner.post(
            f"/api/v1/repair-sessions/{session_id}/lease/acquire",
            headers=_session_headers(device_b),
        )
        assert blocked.status_code == 409
        assert _error_code(blocked) == "REPAIR_SESSION_LEASE_HELD"

        takeover = owner.post(
            f"/api/v1/repair-sessions/{session_id}/lease/takeover",
            headers=_session_headers(device_b),
        )
        assert takeover.status_code == 200, takeover.text
        assert takeover.json()["lease"]["status"] == "owned"

        old_device_pause = owner.post(
            f"/api/v1/repair-sessions/{session_id}/pause",
            headers=_session_headers(device_a, "pause_old_device"),
        )
        assert old_device_pause.status_code == 409
        assert _error_code(old_device_pause) == "REPAIR_SESSION_LEASE_HELD"

        paused = owner.post(
            f"/api/v1/repair-sessions/{session_id}/pause",
            headers=_session_headers(device_b, "pause_session_01"),
        )
        assert paused.status_code == 200, paused.text
        assert paused.json()["session"]["status"] == "paused"
        assert paused.json()["event"]["sequence"] == 2

        pause_retry = owner.post(
            f"/api/v1/repair-sessions/{session_id}/pause",
            headers=_session_headers(device_b, "pause_session_01"),
        )
        assert pause_retry.status_code == 200, pause_retry.text
        assert pause_retry.json()["event"]["id"] == paused.json()["event"]["id"]
        assert pause_retry.json()["session"]["current_sequence"] == 2

        invalid_second_pause = owner.post(
            f"/api/v1/repair-sessions/{session_id}/pause",
            headers=_session_headers(device_b, "pause_session_02"),
        )
        assert invalid_second_pause.status_code == 409
        assert _error_code(invalid_second_pause) == "REPAIR_SESSION_STATE_CONFLICT"

        resumed = owner.post(
            f"/api/v1/repair-sessions/{session_id}/resume",
            headers=_session_headers(device_b, "resume_session_01"),
        )
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["session"]["status"] == "active"
        assert resumed.json()["event"]["sequence"] == 3

        history_page = owner.get(
            f"/api/v1/repair-sessions/{session_id}/events?after_sequence=0&limit=2"
        )
        assert history_page.status_code == 200
        history = history_page.json()
        assert [item["sequence"] for item in history["items"]] == [1, 2]
        assert history["next_after_sequence"] == 2

        next_page = owner.get(
            f"/api/v1/repair-sessions/{session_id}/events?after_sequence=2&limit=2"
        )
        assert [item["sequence"] for item in next_page.json()["items"]] == [3]
        assert next_page.json()["next_after_sequence"] is None

        archived = owner.patch(
            f"/api/v1/repair-sessions/{session_id}/archive",
            headers=_session_headers(device_b, "archive_session_01"),
        )
        assert archived.status_code == 200, archived.text
        assert archived.json()["session"]["status"] == "archived"
        assert archived.json()["lease"]["status"] == "available"

        read_archived = owner.get(f"/api/v1/repair-sessions/{session_id}/resume")
        assert read_archived.status_code == 200
        assert read_archived.json()["session"]["status"] == "archived"

        edit_archived = owner.post(
            f"/api/v1/repair-sessions/{session_id}/lease/acquire",
            headers=_session_headers(device_a),
        )
        assert edit_archived.status_code == 409
        assert _error_code(edit_archived) == "REPAIR_SESSION_ARCHIVED"

        active_list = owner.get("/api/v1/repair-sessions")
        assert active_list.status_code == 200
        assert all(item["id"] != session_id for item in active_list.json())

        full_list = owner.get("/api/v1/repair-sessions?include_archived=true")
        assert any(item["id"] == session_id for item in full_list.json())


def test_headers_and_archived_vehicle_preconditions_are_coded() -> None:
    with TestClient(app) as owner:
        _register(owner, "repair_input")
        vehicle_id = _create_vehicle(owner)

        missing_device = owner.post(
            "/api/v1/repair-sessions",
            json={"user_vehicle_id": vehicle_id, "title": "Repair"},
            headers={**CSRF, "Idempotency-Key": "valid_key_01"},
        )
        assert missing_device.status_code == 422
        assert _error_code(missing_device) == "REPAIR_SESSION_DEVICE_ID_INVALID"

        invalid_device = owner.post(
            "/api/v1/repair-sessions",
            json={"user_vehicle_id": vehicle_id, "title": "Repair"},
            headers=_session_headers("not-a-uuid", "valid_key_02"),
        )
        assert invalid_device.status_code == 422
        assert _error_code(invalid_device) == "REPAIR_SESSION_DEVICE_ID_INVALID"

        missing_key = owner.post(
            "/api/v1/repair-sessions",
            json={"user_vehicle_id": vehicle_id, "title": "Repair"},
            headers=_session_headers(str(uuid4())),
        )
        assert missing_key.status_code == 422
        assert _error_code(missing_key) == "REPAIR_SESSION_IDEMPOTENCY_INVALID"

        archived_vehicle = owner.patch(
            f"/api/v1/user-vehicles/{vehicle_id}/archive",
            headers=CSRF,
        )
        assert archived_vehicle.status_code == 200
        blocked = _create_session(
            owner,
            vehicle_id=vehicle_id,
            device_id=str(uuid4()),
            key="archived_vehicle_01",
        )
        assert blocked.status_code == 409
        assert _error_code(blocked) == "USER_VEHICLE_ARCHIVED"


def test_repair_session_is_private_and_event_table_is_append_only() -> None:
    device_id = str(uuid4())
    with TestClient(app) as owner, TestClient(app) as stranger:
        owner_id = _register(owner, "repair_private")
        _register(stranger, "repair_stranger")
        vehicle_id = _create_vehicle(owner)
        created = _create_session(
            owner,
            vehicle_id=vehicle_id,
            device_id=device_id,
            key="private_session_01",
        )
        assert created.status_code == 201, created.text
        session_id = created.json()["session"]["id"]

        for method, path in (
            ("get", f"/api/v1/repair-sessions/{session_id}/resume"),
            ("get", f"/api/v1/repair-sessions/{session_id}/events"),
        ):
            response = getattr(stranger, method)(path)
            assert response.status_code == 404
            assert _error_code(response) == "REPAIR_SESSION_NOT_FOUND"

        stranger_takeover = stranger.post(
            f"/api/v1/repair-sessions/{session_id}/lease/takeover",
            headers=_session_headers(str(uuid4())),
        )
        assert stranger_takeover.status_code == 404
        assert _error_code(stranger_takeover) == "REPAIR_SESSION_NOT_FOUND"

    async def forbidden_event_update() -> None:
        async with session_factory() as db:
            async with db.begin():
                await db.execute(text("SET LOCAL ROLE partgraph_app"))
                await set_user_context(db, UUID(owner_id))
                with pytest.raises(DBAPIError):
                    await db.execute(
                        update(RepairSessionEvent)
                        .where(RepairSessionEvent.session_id == UUID(session_id))
                        .values(event_type="session_archived")
                    )

    asyncio.run(forbidden_event_update())


def test_expired_lease_requires_reacquire() -> None:
    device_id = str(uuid4())
    with TestClient(app) as owner:
        owner_id = _register(owner, "repair_expiry")
        vehicle_id = _create_vehicle(owner)
        created = _create_session(
            owner,
            vehicle_id=vehicle_id,
            device_id=device_id,
            key="expiry_session_01",
        )
        session_id = created.json()["session"]["id"]

        async def expire() -> None:
            async with session_factory() as db:
                async with db.begin():
                    await db.execute(
                        update(RepairSessionProjection)
                        .where(RepairSessionProjection.session_id == UUID(session_id))
                        .values(editor_lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
                    )

        asyncio.run(expire())

        blocked = owner.post(
            f"/api/v1/repair-sessions/{session_id}/pause",
            headers=_session_headers(device_id, "expiry_pause_01"),
        )
        assert blocked.status_code == 409
        assert _error_code(blocked) == "REPAIR_SESSION_LEASE_REQUIRED"

        reacquire = owner.post(
            f"/api/v1/repair-sessions/{session_id}/lease/acquire",
            headers=_session_headers(device_id),
        )
        assert reacquire.status_code == 200
        paused = owner.post(
            f"/api/v1/repair-sessions/{session_id}/pause",
            headers=_session_headers(device_id, "expiry_pause_02"),
        )
        assert paused.status_code == 200

        assert owner_id


def test_projection_is_rebuilt_from_event_history_when_missing_or_stale() -> None:
    device_id = str(uuid4())
    with TestClient(app) as owner:
        owner_id = _register(owner, "repair_rebuild")
        vehicle_id = _create_vehicle(owner)
        created = _create_session(
            owner,
            vehicle_id=vehicle_id,
            device_id=device_id,
            key="rebuild_session_01",
        )
        session_id = created.json()["session"]["id"]
        paused = owner.post(
            f"/api/v1/repair-sessions/{session_id}/pause",
            headers=_session_headers(device_id, "rebuild_pause_01"),
        )
        assert paused.status_code == 200

        async def remove_projection() -> None:
            async with session_factory() as db:
                async with db.begin():
                    await db.execute(
                        delete(RepairSessionProjection).where(
                            RepairSessionProjection.session_id == UUID(session_id)
                        )
                    )

        asyncio.run(remove_projection())
        rebuilt = owner.get(f"/api/v1/repair-sessions/{session_id}/resume")
        assert rebuilt.status_code == 200, rebuilt.text
        assert rebuilt.json()["session"]["status"] == "paused"
        assert rebuilt.json()["session"]["current_sequence"] == 2

        async def make_stale() -> None:
            async with session_factory() as db:
                async with db.begin():
                    await db.execute(
                        update(RepairSessionProjection)
                        .where(RepairSessionProjection.session_id == UUID(session_id))
                        .values(current_sequence=1)
                    )

        asyncio.run(make_stale())
        repaired_again = owner.get(f"/api/v1/repair-sessions/{session_id}/resume")
        assert repaired_again.status_code == 200
        assert repaired_again.json()["session"]["current_sequence"] == 2
        assert repaired_again.json()["session"]["status"] == "paused"
        assert owner_id


def test_concurrent_mutations_are_serialized_and_same_key_is_deduplicated() -> None:
    device_id = str(uuid4())
    with TestClient(app) as owner:
        _register(owner, "repair_race")
        vehicle_id = _create_vehicle(owner)
        created = _create_session(
            owner,
            vehicle_id=vehicle_id,
            device_id=device_id,
            key="race_session_01",
        )
        session_id = created.json()["session"]["id"]
        token = owner.cookies.get("partgraph_session")
        assert token

    def pause(key: str):
        with TestClient(app) as client:
            client.cookies.set("partgraph_session", token)
            return client.post(
                f"/api/v1/repair-sessions/{session_id}/pause",
                headers=_session_headers(device_id, key),
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(pause, ["race_pause_a1", "race_pause_b1"]))
    codes = sorted(response.status_code for response in results)
    assert codes == [200, 409]
    failed = next(response for response in results if response.status_code == 409)
    assert _error_code(failed) == "REPAIR_SESSION_STATE_CONFLICT"

    with TestClient(app) as owner:
        owner.cookies.set("partgraph_session", token)
        resumed = owner.post(
            f"/api/v1/repair-sessions/{session_id}/resume",
            headers=_session_headers(device_id, "race_resume_01"),
        )
        assert resumed.status_code == 200

    with ThreadPoolExecutor(max_workers=2) as pool:
        duplicate_results = list(pool.map(pause, ["race_same_key1", "race_same_key1"]))
    assert [response.status_code for response in duplicate_results] == [200, 200]
    event_ids = {response.json()["event"]["id"] for response in duplicate_results}
    assert len(event_ids) == 1

    async def count_events() -> int:
        async with session_factory() as db:
            return int(
                await db.scalar(
                    select(text("count(*)")).select_from(RepairSessionEvent).where(
                        RepairSessionEvent.session_id == UUID(session_id),
                        RepairSessionEvent.idempotency_key == "race_same_key1",
                    )
                )
            )

    assert asyncio.run(count_events()) == 1
