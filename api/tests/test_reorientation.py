from uuid import uuid4

from fastapi.testclient import TestClient

from partgraph.main import app

CSRF = {"X-PartGraph-CSRF": "1"}
PASSWORD = "correct-horse-battery-staple"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"partgraph-resume-image"


def _register(client: TestClient, prefix: str) -> None:
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


def _vehicle(client: TestClient) -> str:
    response = client.post(
        "/api/v1/user-vehicles/manual",
        json={
            "nickname": "Resume car",
            "selection": {
                "year": 2009,
                "market": "US",
                "make": "Honda",
                "model": f"Resume-{uuid4().hex[:8]}",
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


def _session(client: TestClient, device_id: str) -> tuple[str, dict]:
    response = client.post(
        "/api/v1/repair-sessions",
        json={"user_vehicle_id": _vehicle(client), "title": "Front cooling repair"},
        headers=_headers(device_id, "resume_session_01"),
    )
    assert response.status_code == 201, response.text
    return response.json()["session"]["id"], response.json()


def test_new_session_resume_is_complete_without_inventing_guidance() -> None:
    device_id = str(uuid4())
    with TestClient(app) as client:
        _register(client, "resume_empty")
        session_id, created = _session(client, device_id)

        reorientation = created["reorientation"]
        assert reorientation is not None
        assert reorientation["checkpoint"]["event_type"] == "session_started"
        assert reorientation["attention"] == []
        assert reorientation["storage_groups"] == []
        assert reorientation["recent_observations"] == []
        assert reorientation["recent_evidence"] == []
        assert reorientation["counts"] == {
            "fasteners_total": 0,
            "hardware_not_installed": 0,
            "hardware_stored": 0,
            "hardware_loose": 0,
            "inventory_total": 0,
            "procurement_blockers": 0,
            "observations_total": 0,
            "photos_total": 0,
        }
        assert reorientation["next_verified_action"] == {
            "status": "unavailable",
            "label": None,
            "reason": "repair_plan_not_available",
        }

        resumed = client.get(
            f"/api/v1/repair-sessions/{session_id}/resume",
            headers={"X-PartGraph-Device-ID": device_id},
        )
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["reorientation"] == reorientation


def test_resume_summarizes_normal_hardware_and_surfaces_only_exceptions() -> None:
    device_a = str(uuid4())
    device_b = str(uuid4())
    with TestClient(app) as client:
        _register(client, "resume_state")
        session_id, _ = _session(client, device_a)

        location = client.post(
            f"/api/v1/repair-sessions/{session_id}/storage-locations",
            json={"label": "Magnetic tray A"},
            headers=_headers(device_a, "resume_location_01"),
        )
        assert location.status_code == 201, location.text
        location_id = location.json()["id"]

        stored = client.post(
            f"/api/v1/repair-sessions/{session_id}/fasteners",
            json={
                "label": "Upper support bolts",
                "origin": "Upper radiator support",
                "physical_state": "stored",
                "storage_location_id": location_id,
            },
            headers=_headers(device_a, "resume_fastener_stored"),
        )
        assert stored.status_code == 201, stored.text

        removed = client.post(
            f"/api/v1/repair-sessions/{session_id}/fasteners",
            json={"label": "Center clip", "physical_state": "removed"},
            headers=_headers(device_a, "resume_fastener_removed"),
        )
        assert removed.status_code == 201, removed.text

        missing = client.post(
            f"/api/v1/repair-sessions/{session_id}/fasteners",
            json={
                "label": "Lower splash-shield clip",
                "origin": "Front underbody shield",
                "physical_state": "missing",
            },
            headers=_headers(device_a, "resume_fastener_missing"),
        )
        assert missing.status_code == 201, missing.text

        needed = client.post(
            f"/api/v1/repair-sessions/{session_id}/inventory",
            json={"name": "Replacement splash-shield clip", "procurement_state": "needed"},
            headers=_headers(device_a, "resume_inventory_needed"),
        )
        assert needed.status_code == 201, needed.text

        available = client.post(
            f"/api/v1/repair-sessions/{session_id}/inventory",
            json={"name": "Coolant funnel", "procurement_state": "available"},
            headers=_headers(device_a, "resume_inventory_available"),
        )
        assert available.status_code == 201, available.text

        damage = client.post(
            f"/api/v1/repair-sessions/{session_id}/observations",
            json={"category": "damage", "text": "Lower clip cracked during removal."},
            headers=_headers(device_a, "resume_observation_damage"),
        )
        assert damage.status_code == 201, damage.text

        condition = client.post(
            f"/api/v1/repair-sessions/{session_id}/observations",
            json={"category": "condition", "text": "Upper support bolts are grouped together."},
            headers=_headers(device_a, "resume_observation_condition"),
        )
        assert condition.status_code == 201, condition.text

        photo = client.post(
            f"/api/v1/repair-sessions/{session_id}/photos",
            data={"purpose": "before"},
            files={"photo": ("before.png", PNG_BYTES, "image/png")},
            headers=_headers(device_a, "resume_photo_01"),
        )
        assert photo.status_code == 201, photo.text
        photo_id = photo.json()["id"]

        paused = client.post(
            f"/api/v1/repair-sessions/{session_id}/pause",
            headers=_headers(device_a, "resume_pause_01"),
        )
        assert paused.status_code == 200, paused.text
        paused_sequence = paused.json()["event"]["sequence"]

        viewer = client.get(
            f"/api/v1/repair-sessions/{session_id}/resume",
            headers={"X-PartGraph-Device-ID": device_b},
        )
        assert viewer.status_code == 200, viewer.text
        payload = viewer.json()
        assert payload["session"]["status"] == "paused"
        assert payload["session"]["current_sequence"] == paused_sequence
        assert payload["last_event"]["event_type"] == "session_paused"
        assert payload["lease"]["status"] == "held_by_other"
        assert payload["lease"]["can_edit"] is False

        resume = payload["reorientation"]
        assert resume["checkpoint"]["event_type"] == "photo_evidence_added"
        assert resume["counts"] == {
            "fasteners_total": 3,
            "hardware_not_installed": 3,
            "hardware_stored": 1,
            "hardware_loose": 1,
            "inventory_total": 2,
            "procurement_blockers": 1,
            "observations_total": 2,
            "photos_total": 1,
        }
        assert resume["storage_groups"] == [
            {
                "storage_location_id": location_id,
                "label": "Magnetic tray A",
                "item_count": 1,
            }
        ]

        attention = {(item["kind"], item["label"], item["severity"]) for item in resume["attention"]}
        assert attention == {
            ("fastener", "Lower splash-shield clip", "blocking"),
            ("inventory", "Replacement splash-shield clip", "blocking"),
            ("observation", "Damage observation", "attention"),
        }
        assert all(item["label"] != "Upper support bolts" for item in resume["attention"])
        assert all(item["label"] != "Coolant funnel" for item in resume["attention"])

        assert resume["recent_evidence"][0]["id"] == photo_id
        assert resume["recent_evidence"][0]["content_url"].endswith(f"/{photo_id}/content")
        assert resume["recent_observations"][0]["text"] == (
            "Upper support bolts are grouped together."
        )
        assert any(item["event_type"] == "session_paused" for item in resume["recent_activity"])
        assert resume["next_verified_action"]["status"] == "unavailable"
        assert resume["next_verified_action"]["reason"] == "repair_plan_not_available"

        second_read = client.get(
            f"/api/v1/repair-sessions/{session_id}/resume",
            headers={"X-PartGraph-Device-ID": device_b},
        )
        assert second_read.status_code == 200
        assert second_read.json()["session"]["current_sequence"] == paused_sequence


def test_reorientation_keeps_cross_user_session_private() -> None:
    device_id = str(uuid4())
    with TestClient(app) as owner, TestClient(app) as stranger:
        _register(owner, "resume_owner")
        _register(stranger, "resume_stranger")
        session_id, _ = _session(owner, device_id)

        response = stranger.get(f"/api/v1/repair-sessions/{session_id}/resume")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "REPAIR_SESSION_NOT_FOUND"
