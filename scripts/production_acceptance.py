from __future__ import annotations

import http.cookiejar
import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

BASE_URL = os.getenv("PARTGRAPH_PRODUCTION_URL", "https://partgraph-main.vercel.app").rstrip("/")
CSRF = {"X-PartGraph-CSRF": "1"}
EXPECTED_ORIGIN = BASE_URL


@dataclass
class Result:
    status: int
    headers: Any
    text: str

    def json(self) -> Any:
        return json.loads(self.text) if self.text else None


class Client:
    def __init__(self) -> None:
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> Result:
        data = None
        request_headers = {"User-Agent": "PartGraph-Production-Acceptance/1"}
        if headers:
            request_headers.update(headers)
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        request = urllib.request.Request(
            f"{BASE_URL}{path}",
            data=data,
            headers=request_headers,
            method=method,
        )
        try:
            with self.opener.open(request, timeout=30) as response:
                return Result(
                    status=response.status,
                    headers=response.headers,
                    text=response.read().decode("utf-8"),
                )
        except urllib.error.HTTPError as exc:
            return Result(
                status=exc.code,
                headers=exc.headers,
                text=exc.read().decode("utf-8"),
            )


def error_code(result: Result) -> str | None:
    try:
        payload = result.json()
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    return error.get("code") if isinstance(error, dict) else None


def expect(result: Result, status: int, label: str) -> Any:
    if result.status != status:
        raise AssertionError(
            f"{label}: expected HTTP {status}, got {result.status}; "
            f"code={error_code(result)!r}; body={result.text[:500]!r}"
        )
    api_version = result.headers.get("X-PartGraph-API-Version")
    if api_version != "v1":
        raise AssertionError(f"{label}: missing/wrong API version header: {api_version!r}")
    print(f"PASS {label}: HTTP {status}")
    return result.json()


def mutation_headers(device_id: str) -> dict[str, str]:
    return {
        **CSRF,
        "X-PartGraph-Device-ID": device_id,
        "Idempotency-Key": f"qa_{uuid4().hex[:24]}",
    }


def main() -> None:
    suffix = uuid4().hex[:10]
    password_a = "ProdQa_" + secrets.token_urlsafe(18)
    password_b = "ProdQa_" + secrets.token_urlsafe(18)
    email_a = f"qa-partgraph-a-{suffix}@example.com"
    email_b = f"qa-partgraph-b-{suffix}@example.com"
    username_a = f"qa_prod_a_{suffix}"
    username_b = f"qa_prod_b_{suffix}"
    device_a = str(uuid4())

    public = Client()
    live = expect(public.request("GET", "/api/v1/health/live"), 200, "live health")
    assert live == {"service": "partgraph-api", "status": "ok"}

    ready = expect(public.request("GET", "/api/v1/health/ready"), 200, "database readiness")
    assert ready["database"] == "ready"

    configs = expect(
        public.request("GET", "/api/v1/vehicle-configurations?limit=5"),
        200,
        "vehicle catalog read",
    )
    catalog_empty = configs == []
    print(f"INFO canonical vehicle catalog empty={catalog_empty}")

    csrf_candidate = {
        "email": f"qa-csrf-{suffix}@example.com",
        "username": f"qa_csrf_{suffix}",
        "password": "ProdQa_" + secrets.token_urlsafe(18),
    }
    missing_csrf = public.request("POST", "/api/v1/auth/register", payload=csrf_candidate)
    expect(missing_csrf, 403, "CSRF required")
    assert error_code(missing_csrf) == "AUTH_CSRF_FAILED"

    foreign = public.request(
        "POST",
        "/api/v1/auth/register",
        payload=csrf_candidate,
        headers={**CSRF, "Origin": "https://attacker.invalid"},
    )
    expect(foreign, 403, "foreign origin rejected")
    assert error_code(foreign) == "AUTH_ORIGIN_REJECTED"

    allowed_preflight = public.request(
        "OPTIONS",
        "/api/v1/auth/login",
        headers={
            "Origin": EXPECTED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-partgraph-csrf,x-request-id",
        },
    )
    if allowed_preflight.status != 200:
        raise AssertionError(f"allowed CORS preflight: HTTP {allowed_preflight.status}")
    assert allowed_preflight.headers.get("Access-Control-Allow-Origin") == EXPECTED_ORIGIN
    assert allowed_preflight.headers.get("Access-Control-Allow-Credentials") == "true"
    print("PASS allowed CORS origin")

    denied_preflight = public.request(
        "OPTIONS",
        "/api/v1/auth/login",
        headers={
            "Origin": "https://attacker.invalid",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert denied_preflight.headers.get("Access-Control-Allow-Origin") is None
    print("PASS foreign CORS origin not allowed")

    a = Client()
    registered_a_result = a.request(
        "POST",
        "/api/v1/auth/register",
        payload={"email": email_a, "username": username_a, "password": password_a},
        headers=CSRF,
    )
    registered_a = expect(registered_a_result, 200, "owner A registration")
    user_a_id = registered_a["user"]["id"]
    set_cookie = registered_a_result.headers.get("Set-Cookie", "")
    for required in ("HttpOnly", "Secure", "SameSite=lax"):
        if required not in set_cookie:
            raise AssertionError(f"owner A session cookie missing {required}")
    assert "token" not in registered_a
    print("PASS secure HttpOnly session cookie")

    me_a = expect(a.request("GET", "/api/v1/auth/me"), 200, "owner A authenticated session")
    assert me_a["user"]["id"] == user_a_id

    prefs = expect(a.request("GET", "/api/v1/account/preferences"), 200, "owner A preferences")
    assert prefs["units"] == "us_customary"
    changed = expect(
        a.request(
            "PATCH",
            "/api/v1/account/preferences",
            payload={"units": "metric"},
            headers=CSRF,
        ),
        200,
        "owner A preference persistence",
    )
    assert changed["units"] == "metric"

    vehicle = expect(
        a.request(
            "POST",
            "/api/v1/user-vehicles/manual",
            payload={
                "nickname": "QA 2009 Civic",
                "selection": {
                    "year": 2009,
                    "market": "US",
                    "make": "Honda",
                    "model": "Civic",
                },
            },
            headers=CSRF,
        ),
        201,
        "owner A manual vehicle save",
    )
    vehicle_id = vehicle["id"]
    assert vehicle["identity_source"] == "manual"
    assert vehicle["masked_vin"] is None
    if catalog_empty:
        assert vehicle["canonical_configuration_id"] is None
        assert vehicle["identity_resolution"] == "manual_candidate"
    print(f"INFO owner A vehicle_id={vehicle_id}")

    vehicles_a = expect(a.request("GET", "/api/v1/user-vehicles"), 200, "owner A garage list")
    assert any(row["id"] == vehicle_id for row in vehicles_a)

    created_session = expect(
        a.request(
            "POST",
            "/api/v1/repair-sessions",
            payload={"user_vehicle_id": vehicle_id, "title": "QA production repair"},
            headers=mutation_headers(device_a),
        ),
        201,
        "owner A repair session create",
    )
    session_id = created_session["session"]["id"]
    assert created_session["session"]["status"] == "active"
    assert created_session["lease"]["can_edit"] is True
    print(f"INFO owner A session_id={session_id}")

    repair_options = expect(
        a.request("GET", f"/api/v1/repair-sessions/{session_id}/repair-options"),
        200,
        "repair option resolution",
    )
    if catalog_empty:
        assert repair_options["vehicle_resolution"] == "unresolved"
        assert repair_options["options"] == []
        print("PASS empty knowledge fails closed: no guessed repair options")

    storage = expect(
        a.request(
            "POST",
            f"/api/v1/repair-sessions/{session_id}/storage-locations",
            payload={"label": "QA parts tray", "notes": "synthetic production acceptance"},
            headers=mutation_headers(device_a),
        ),
        201,
        "repair memory storage location",
    )

    fastener = expect(
        a.request(
            "POST",
            f"/api/v1/repair-sessions/{session_id}/fasteners",
            payload={
                "label": "QA upper support bolt",
                "origin": "upper support",
                "position": "left",
                "physical_state": "stored",
                "storage_location_id": storage["id"],
                "notes": "synthetic production acceptance",
            },
            headers=mutation_headers(device_a),
        ),
        201,
        "repair memory fastener",
    )
    assert fastener["storage_location_id"] == storage["id"]

    inventory = expect(
        a.request(
            "POST",
            f"/api/v1/repair-sessions/{session_id}/inventory",
            payload={
                "name": "QA replacement clip",
                "quantity": 2,
                "procurement_state": "ordered",
                "reference": "QA-CLIP",
                "notes": "synthetic production acceptance",
            },
            headers=mutation_headers(device_a),
        ),
        201,
        "repair memory inventory",
    )
    assert inventory["procurement_state"] == "ordered"

    observation = expect(
        a.request(
            "POST",
            f"/api/v1/repair-sessions/{session_id}/observations",
            payload={
                "category": "condition",
                "text": "Synthetic QA observation for hosted acceptance.",
                "fastener_id": fastener["id"],
            },
            headers=mutation_headers(device_a),
        ),
        201,
        "repair memory observation",
    )
    assert observation["source"] == "user"
    assert observation["review_state"] == "confirmed"

    paused = expect(
        a.request(
            "POST",
            f"/api/v1/repair-sessions/{session_id}/pause",
            headers=mutation_headers(device_a),
        ),
        200,
        "repair session pause",
    )
    assert paused["session"]["status"] == "paused"

    paused_snapshot = expect(
        a.request(
            "GET",
            f"/api/v1/repair-sessions/{session_id}/resume",
            headers={"X-PartGraph-Device-ID": device_a},
        ),
        200,
        "paused session resume snapshot",
    )
    assert paused_snapshot["session"]["status"] == "paused"
    assert paused_snapshot["reorientation"] is not None
    assert paused_snapshot["reorientation"]["counts"]["fasteners_total"] >= 1
    assert paused_snapshot["reorientation"]["counts"]["inventory_total"] >= 1
    assert paused_snapshot["reorientation"]["counts"]["observations_total"] >= 1

    resumed = expect(
        a.request(
            "POST",
            f"/api/v1/repair-sessions/{session_id}/resume",
            headers=mutation_headers(device_a),
        ),
        200,
        "repair session resume",
    )
    assert resumed["session"]["status"] == "active"

    events = expect(
        a.request("GET", f"/api/v1/repair-sessions/{session_id}/events?limit=100"),
        200,
        "append-only event history",
    )
    event_types = [item["event_type"] for item in events["items"]]
    for required_event in (
        "session_started",
        "storage_location_created",
        "fastener_recorded",
        "inventory_item_recorded",
        "observation_recorded",
        "session_paused",
        "session_resumed",
    ):
        if required_event not in event_types:
            raise AssertionError(f"missing event {required_event}: {event_types}")
    sequences = [item["sequence"] for item in events["items"]]
    assert sequences == sorted(sequences)
    assert len(sequences) == len(set(sequences))
    print("PASS ordered append-only event projection")

    b = Client()
    registered_b = expect(
        b.request(
            "POST",
            "/api/v1/auth/register",
            payload={"email": email_b, "username": username_b, "password": password_b},
            headers=CSRF,
        ),
        200,
        "owner B registration",
    )
    assert registered_b["user"]["id"] != user_a_id

    b_vehicles = expect(b.request("GET", "/api/v1/user-vehicles"), 200, "owner B garage isolation")
    assert b_vehicles == []

    foreign_vehicle = b.request("GET", f"/api/v1/user-vehicles/{vehicle_id}")
    expect(foreign_vehicle, 404, "owner B cannot read owner A vehicle")
    assert error_code(foreign_vehicle) == "USER_VEHICLE_NOT_FOUND"

    foreign_session = b.request("GET", f"/api/v1/repair-sessions/{session_id}/resume")
    expect(foreign_session, 404, "owner B cannot read owner A repair session")
    assert error_code(foreign_session) == "REPAIR_SESSION_NOT_FOUND"

    foreign_observations = b.request(
        "GET", f"/api/v1/repair-sessions/{session_id}/observations"
    )
    expect(foreign_observations, 404, "owner B cannot read owner A repair memory")
    assert error_code(foreign_observations) == "REPAIR_SESSION_NOT_FOUND"

    archived_session = expect(
        a.request(
            "PATCH",
            f"/api/v1/repair-sessions/{session_id}/archive",
            headers=mutation_headers(device_a),
        ),
        200,
        "owner A repair session archive",
    )
    assert archived_session["session"]["status"] == "archived"
    assert archived_session["session"]["archived_at"] is not None

    archived_vehicle = expect(
        a.request(
            "PATCH",
            f"/api/v1/user-vehicles/{vehicle_id}/archive",
            headers=CSRF,
        ),
        200,
        "owner A vehicle archive",
    )
    assert archived_vehicle["archived_at"] is not None

    expect(a.request("POST", "/api/v1/auth/logout", headers=CSRF), 204, "owner A logout")
    signed_out_a = a.request("GET", "/api/v1/auth/me")
    expect(signed_out_a, 401, "owner A session revoked after logout")
    assert error_code(signed_out_a) in {"AUTH_REQUIRED", "AUTH_SESSION_REVOKED"}

    expect(b.request("POST", "/api/v1/auth/logout", headers=CSRF), 204, "owner B logout")

    print(
        "RESULT "
        + json.dumps(
            {
                "status": "PASS",
                "catalog_empty": catalog_empty,
                "owner_state_flow": "pass",
                "cross_owner_isolation": "pass",
                "pause_resume": "pass",
                "repair_memory": "pass",
                "guided_repair": "blocked_by_empty_canonical_catalog"
                if catalog_empty
                else "not_exercised_by_this_probe",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"RESULT FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
