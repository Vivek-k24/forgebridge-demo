import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from partgraph.auth.service import set_user_context
from partgraph.config import settings
from partgraph.database import session_factory
from partgraph.errors import PartGraphError
from partgraph.main import app
from partgraph.repair_memory.models import RepairFastener
from partgraph.repair_memory.storage import photo_path

CSRF = {"X-PartGraph-CSRF": "1"}
PASSWORD = "correct-horse-battery-staple"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"partgraph-test-image"


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
    return str(payload["error"]["code"])


def _create_vehicle(client: TestClient) -> str:
    response = client.post(
        "/api/v1/user-vehicles/manual",
        json={
            "nickname": "Memory test car",
            "selection": {
                "year": 2009,
                "market": "US",
                "make": "Honda",
                "model": f"Memory-{uuid4().hex[:8]}",
                "trim": "Hybrid",
            },
        },
        headers=CSRF,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _headers(device_id: str, key: str | None = None) -> dict[str, str]:
    headers = {**CSRF, "X-PartGraph-Device-ID": device_id}
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def _create_session(client: TestClient, vehicle_id: str, device_id: str) -> str:
    response = client.post(
        "/api/v1/repair-sessions",
        json={"user_vehicle_id": vehicle_id, "title": "Front repair memory"},
        headers=_headers(device_id, "memory_session_01"),
    )
    assert response.status_code == 201, response.text
    return response.json()["session"]["id"]


def test_physical_memory_flow_is_idempotent_and_preserves_session_status() -> None:
    device_id = str(uuid4())
    with TestClient(app) as client:
        _register(client, "memory_flow")
        session_id = _create_session(client, _create_vehicle(client), device_id)

        location = client.post(
            f"/api/v1/repair-sessions/{session_id}/storage-locations",
            json={"label": "Magnetic tray A", "notes": "Left side of workbench"},
            headers=_headers(device_id, "memory_location_01"),
        )
        assert location.status_code == 201, location.text
        location_id = location.json()["id"]

        fastener_payload = {
            "kind": "fastener",
            "label": "Upper support bolt",
            "origin": "Upper radiator support",
            "position": "Driver side",
            "physical_state": "stored",
            "storage_location_id": location_id,
        }
        fastener = client.post(
            f"/api/v1/repair-sessions/{session_id}/fasteners",
            json=fastener_payload,
            headers=_headers(device_id, "memory_fastener_01"),
        )
        assert fastener.status_code == 201, fastener.text
        fastener_id = fastener.json()["id"]
        retry = client.post(
            f"/api/v1/repair-sessions/{session_id}/fasteners",
            json=fastener_payload,
            headers=_headers(device_id, "memory_fastener_01"),
        )
        assert retry.status_code == 201
        assert retry.json()["id"] == fastener_id

        conflict = client.post(
            f"/api/v1/repair-sessions/{session_id}/fasteners",
            json={**fastener_payload, "label": "Different bolt"},
            headers=_headers(device_id, "memory_fastener_01"),
        )
        assert conflict.status_code == 409
        assert _error_code(conflict) == "REPAIR_SESSION_IDEMPOTENCY_CONFLICT"

        invalid_storage = client.patch(
            f"/api/v1/repair-sessions/{session_id}/fasteners/{fastener_id}",
            json={"physical_state": "stored"},
            headers=_headers(device_id, "memory_fastener_invalid"),
        )
        assert invalid_storage.status_code == 422

        inventory = client.post(
            f"/api/v1/repair-sessions/{session_id}/inventory",
            json={"name": "Replacement support bolt", "quantity": 1, "procurement_state": "needed"},
            headers=_headers(device_id, "memory_inventory_01"),
        )
        assert inventory.status_code == 201, inventory.text
        inventory_id = inventory.json()["id"]
        available = client.patch(
            f"/api/v1/repair-sessions/{session_id}/inventory/{inventory_id}",
            json={"procurement_state": "available"},
            headers=_headers(device_id, "memory_inventory_02"),
        )
        assert available.status_code == 200, available.text
        assert available.json()["procurement_state"] == "available"
        fasteners = client.get(f"/api/v1/repair-sessions/{session_id}/fasteners")
        assert fasteners.status_code == 200
        assert fasteners.json()[0]["physical_state"] == "stored"

        observation = client.post(
            f"/api/v1/repair-sessions/{session_id}/observations",
            json={
                "category": "condition",
                "text": "Bolt threads look reusable after removal.",
                "fastener_id": fastener_id,
            },
            headers=_headers(device_id, "memory_observation_01"),
        )
        assert observation.status_code == 201, observation.text
        observation_id = observation.json()["id"]
        assert observation.json()["source"] == "user"
        assert observation.json()["review_state"] == "confirmed"

        photo = client.post(
            f"/api/v1/repair-sessions/{session_id}/photos",
            data={
                "purpose": "fastener",
                "fastener_id": fastener_id,
                "observation_id": observation_id,
            },
            files={"photo": ("bolt.png", PNG_BYTES, "image/png")},
            headers=_headers(device_id, "memory_photo_01"),
        )
        assert photo.status_code == 201, photo.text
        photo_id = photo.json()["id"]
        content = client.get(
            f"/api/v1/repair-sessions/{session_id}/photos/{photo_id}/content"
        )
        assert content.status_code == 200
        assert content.content == PNG_BYTES
        assert content.headers["cache-control"] == "no-store"

        snapshot = client.get(
            f"/api/v1/repair-sessions/{session_id}/resume",
            headers={"X-PartGraph-Device-ID": device_id},
        )
        assert snapshot.status_code == 200
        assert snapshot.json()["session"]["status"] == "active"
        assert snapshot.json()["last_event"]["event_type"] == "photo_evidence_added"

        history = client.get(f"/api/v1/repair-sessions/{session_id}/events?limit=100")
        assert history.status_code == 200
        event_types = [item["event_type"] for item in history.json()["items"]]
        assert event_types == [
            "session_started",
            "storage_location_created",
            "fastener_recorded",
            "inventory_item_recorded",
            "inventory_state_changed",
            "observation_recorded",
            "photo_evidence_added",
        ]

        deleted = client.delete(
            f"/api/v1/repair-sessions/{session_id}/photos/{photo_id}",
            headers=_headers(device_id, "memory_photo_delete_01"),
        )
        assert deleted.status_code == 200, deleted.text
        assert client.get(
            f"/api/v1/repair-sessions/{session_id}/photos/{photo_id}/content"
        ).status_code == 404
        listed = client.get(f"/api/v1/repair-sessions/{session_id}/photos")
        assert listed.status_code == 200
        assert listed.json() == []


def test_memory_is_user_scoped_and_active_edit_lease_is_enforced() -> None:
    device_a = str(uuid4())
    device_b = str(uuid4())
    with TestClient(app) as owner, TestClient(app) as stranger:
        owner_id = _register(owner, "memory_owner")
        stranger_id = _register(stranger, "memory_stranger")
        session_id = _create_session(owner, _create_vehicle(owner), device_a)
        fastener = owner.post(
            f"/api/v1/repair-sessions/{session_id}/fasteners",
            json={"label": "Center clip", "physical_state": "removed"},
            headers=_headers(device_a, "memory_private_fastener"),
        )
        assert fastener.status_code == 201

        for suffix in ("fasteners", "inventory", "observations", "photos", "storage-locations"):
            response = stranger.get(f"/api/v1/repair-sessions/{session_id}/{suffix}")
            assert response.status_code == 404
            assert _error_code(response) == "REPAIR_SESSION_NOT_FOUND"

        blocked = owner.post(
            f"/api/v1/repair-sessions/{session_id}/inventory",
            json={"name": "Clip", "procurement_state": "needed"},
            headers=_headers(device_b, "memory_wrong_device"),
        )
        assert blocked.status_code == 409
        assert _error_code(blocked) == "REPAIR_SESSION_LEASE_HELD"

        takeover = owner.post(
            f"/api/v1/repair-sessions/{session_id}/lease/takeover",
            headers=_headers(device_b),
        )
        assert takeover.status_code == 200
        allowed = owner.post(
            f"/api/v1/repair-sessions/{session_id}/inventory",
            json={"name": "Clip", "procurement_state": "needed"},
            headers=_headers(device_b, "memory_new_device"),
        )
        assert allowed.status_code == 201

    async def rls_count(user_id: str) -> int:
        async with session_factory() as db:
            async with db.begin():
                await db.execute(text("SET LOCAL ROLE partgraph_app"))
                await set_user_context(db, UUID(user_id))
                value = await db.scalar(select(func.count()).select_from(RepairFastener))
                return int(value or 0)

    assert asyncio.run(rls_count(owner_id)) >= 1
    assert asyncio.run(rls_count(stranger_id)) == 0


def test_photo_validation_rejects_bad_attachments_oversize_and_traversal() -> None:
    device_id = str(uuid4())
    with TestClient(app) as client:
        _register(client, "memory_photo")
        session_id = _create_session(client, _create_vehicle(client), device_id)

        malformed = client.post(
            f"/api/v1/repair-sessions/{session_id}/photos",
            data={"purpose": "general"},
            files={"photo": ("fake.jpg", b"not-an-image", "image/jpeg")},
            headers=_headers(device_id, "memory_bad_photo"),
        )
        assert malformed.status_code == 415
        assert _error_code(malformed) == "PHOTO_MEDIA_TYPE_UNSUPPORTED"

        missing_fastener = client.post(
            f"/api/v1/repair-sessions/{session_id}/photos",
            data={"purpose": "fastener"},
            files={"photo": ("bolt.png", PNG_BYTES, "image/png")},
            headers=_headers(device_id, "memory_missing_fastener"),
        )
        assert missing_fastener.status_code == 422
        assert _error_code(missing_fastener) == "PHOTO_ATTACHMENT_INVALID"

        oversized_bytes = b"\xff\xd8\xff" + b"x" * settings.photo_max_bytes
        oversized = client.post(
            f"/api/v1/repair-sessions/{session_id}/photos",
            data={"purpose": "general"},
            files={"photo": ("large.jpg", oversized_bytes, "image/jpeg")},
            headers=_headers(device_id, "memory_large_photo"),
        )
        assert oversized.status_code in {413}
        assert _error_code(oversized) in {"PHOTO_TOO_LARGE", "REQUEST_PAYLOAD_TOO_LARGE"}

    with pytest.raises(PartGraphError) as error:
        photo_path("../escape.jpg")
    assert str(error.value.code) == "PHOTO_STORAGE_CORRUPT"
