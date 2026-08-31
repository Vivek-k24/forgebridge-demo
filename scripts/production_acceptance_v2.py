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

    def request(self, method: str, path: str, *, payload: Any = None, headers: dict[str, str] | None = None) -> Result:
        request_headers = {"User-Agent": "PartGraph-Production-Acceptance/2"}
        if headers:
            request_headers.update(headers)
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            request_headers.setdefault("Content-Type", "application/json")
        request = urllib.request.Request(BASE_URL + path, data=data, headers=request_headers, method=method)
        try:
            with self.opener.open(request, timeout=30) as response:
                return Result(response.status, response.headers, response.read().decode())
        except urllib.error.HTTPError as exc:
            return Result(exc.code, exc.headers, exc.read().decode())


def code(result: Result) -> str | None:
    try:
        body = result.json()
    except Exception:
        return None
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        return body["error"].get("code")
    return None


def require(result: Result, expected: int, label: str) -> Any:
    if result.status != expected:
        raise AssertionError(
            f"{label}: expected {expected}, got {result.status}; code={code(result)!r}; body={result.text[:400]!r}"
        )
    api_version = result.headers.get("X-PartGraph-API-Version")
    if api_version != "v1":
        raise AssertionError(f"{label}: wrong API version header {api_version!r}")
    print(f"PASS {label}: HTTP {expected}")
    return result.json()


def edit_headers(device: str) -> dict[str, str]:
    return {
        **CSRF,
        "X-PartGraph-Device-ID": device,
        "Idempotency-Key": "qa_" + uuid4().hex[:24],
    }


def preflight(client: Client, origin: str) -> tuple[int, str | None, str]:
    result = client.request(
        "OPTIONS",
        "/api/v1/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-partgraph-csrf,x-request-id",
        },
    )
    return result.status, result.headers.get("Access-Control-Allow-Origin"), result.text


def main() -> None:
    failures: list[str] = []
    suffix = uuid4().hex[:10]
    public = Client()

    live = require(public.request("GET", "/api/v1/health/live"), 200, "live health")
    assert live["status"] == "ok"
    ready = require(public.request("GET", "/api/v1/health/ready"), 200, "database readiness")
    assert ready["database"] == "ready"

    configs = require(public.request("GET", "/api/v1/vehicle-configurations?limit=5"), 200, "vehicle catalog")
    catalog_empty = configs == []
    print(f"INFO canonical vehicle catalog empty={catalog_empty}")

    csrf_payload = {
        "email": f"qa-csrf-{suffix}@example.com",
        "username": f"qa_csrf_{suffix}",
        "password": "ProdQa_" + secrets.token_urlsafe(18),
    }
    missing = public.request("POST", "/api/v1/auth/register", payload=csrf_payload)
    require(missing, 403, "CSRF required")
    assert code(missing) == "AUTH_CSRF_FAILED"
    hostile = public.request(
        "POST",
        "/api/v1/auth/register",
        payload=csrf_payload,
        headers={**CSRF, "Origin": "https://attacker.invalid"},
    )
    require(hostile, 403, "hostile origin rejected")
    assert code(hostile) == "AUTH_ORIGIN_REJECTED"

    prod_status, prod_allow, prod_body = preflight(public, BASE_URL)
    local_status, local_allow, local_body = preflight(public, "http://localhost:5173")
    prod_cors_ok = prod_status == 200 and prod_allow == BASE_URL
    print(f"INFO CORS production origin: status={prod_status} allow={prod_allow!r} body={prod_body!r}")
    print(f"INFO CORS localhost origin: status={local_status} allow={local_allow!r} body={local_body!r}")
    if not prod_cors_ok:
        failures.append("production CORS origin is not approved")

    a = Client()
    password_a = "ProdQa_" + secrets.token_urlsafe(18)
    registration_a_result = a.request(
        "POST",
        "/api/v1/auth/register",
        payload={
            "email": f"qa-partgraph-a-{suffix}@example.com",
            "username": f"qa_prod_a_{suffix}",
            "password": password_a,
        },
        headers=CSRF,
    )
    registration_a = require(registration_a_result, 200, "owner A registration")
    owner_a = registration_a["user"]["id"]
    assert "token" not in registration_a
    set_cookie = registration_a_result.headers.get("Set-Cookie", "")
    for attribute in ("HttpOnly", "Secure", "SameSite=lax"):
        if attribute not in set_cookie:
            failures.append(f"session cookie missing {attribute}")
    print("PASS owner A session cookie issued")

    me = require(a.request("GET", "/api/v1/auth/me"), 200, "owner A session read")
    assert me["user"]["id"] == owner_a
    prefs = require(a.request("GET", "/api/v1/account/preferences"), 200, "owner A preferences read")
    assert prefs["units"] == "us_customary"
    changed = require(
        a.request("PATCH", "/api/v1/account/preferences", payload={"units": "metric"}, headers=CSRF),
        200,
        "owner A preferences update",
    )
    assert changed["units"] == "metric"

    vehicle = require(
        a.request(
            "POST",
            "/api/v1/user-vehicles/manual",
            payload={
                "nickname": "QA 2009 Civic",
                "selection": {"year": 2009, "market": "US", "make": "Honda", "model": "Civic"},
            },
            headers=CSRF,
        ),
        201,
        "owner A manual vehicle",
    )
    vehicle_id = vehicle["id"]
    assert vehicle["identity_source"] == "manual"
    assert vehicle["masked_vin"] is None
    if catalog_empty:
        assert vehicle["canonical_configuration_id"] is None
        assert vehicle["identity_resolution"] == "manual_candidate"
    garage = require(a.request("GET", "/api/v1/user-vehicles"), 200, "owner A garage")
    assert any(row["id"] == vehicle_id for row in garage)

    device = str(uuid4())
    created = require(
        a.request(
            "POST",
            "/api/v1/repair-sessions",
            payload={"user_vehicle_id": vehicle_id, "title": "QA hosted repair"},
            headers=edit_headers(device),
        ),
        201,
        "repair session create",
    )
    session_id = created["session"]["id"]
    assert created["session"]["status"] == "active"
    assert created["lease"]["can_edit"] is True

    options = require(
        a.request("GET", f"/api/v1/repair-sessions/{session_id}/repair-options"),
        200,
        "repair options",
    )
    if catalog_empty:
        assert options["vehicle_resolution"] == "unresolved"
        assert options["options"] == []
        print("PASS empty catalog fails closed instead of guessing a repair")

    storage = require(
        a.request(
            "POST",
            f"/api/v1/repair-sessions/{session_id}/storage-locations",
            payload={"label": "QA parts tray", "notes": "synthetic hosted test"},
            headers=edit_headers(device),
        ),
        201,
        "repair memory storage",
    )
    fastener = require(
        a.request(
            "POST",
            f"/api/v1/repair-sessions/{session_id}/fasteners",
            payload={
                "label": "QA support bolt",
                "origin": "upper support",
                "position": "left",
                "physical_state": "stored",
                "storage_location_id": storage["id"],
                "notes": "synthetic hosted test",
            },
            headers=edit_headers(device),
        ),
        201,
        "repair memory fastener",
    )
    inventory = require(
        a.request(
            "POST",
            f"/api/v1/repair-sessions/{session_id}/inventory",
            payload={
                "name": "QA replacement clip",
                "quantity": 2,
                "procurement_state": "ordered",
                "reference": "QA-CLIP",
                "notes": "synthetic hosted test",
            },
            headers=edit_headers(device),
        ),
        201,
        "repair memory inventory",
    )
    assert inventory["procurement_state"] == "ordered"
    observation = require(
        a.request(
            "POST",
            f"/api/v1/repair-sessions/{session_id}/observations",
            payload={
                "category": "condition",
                "text": "Synthetic QA observation for hosted acceptance.",
                "fastener_id": fastener["id"],
            },
            headers=edit_headers(device),
        ),
        201,
        "repair memory observation",
    )
    assert observation["source"] == "user"
    assert observation["review_state"] == "confirmed"

    paused = require(
        a.request("POST", f"/api/v1/repair-sessions/{session_id}/pause", headers=edit_headers(device)),
        200,
        "repair session pause",
    )
    assert paused["session"]["status"] == "paused"
    snapshot = require(
        a.request("GET", f"/api/v1/repair-sessions/{session_id}/resume", headers={"X-PartGraph-Device-ID": device}),
        200,
        "pause resume snapshot",
    )
    assert snapshot["session"]["status"] == "paused"
    counts = snapshot["reorientation"]["counts"]
    assert counts["fasteners_total"] >= 1
    assert counts["inventory_total"] >= 1
    assert counts["observations_total"] >= 1
    resumed = require(
        a.request("POST", f"/api/v1/repair-sessions/{session_id}/resume", headers=edit_headers(device)),
        200,
        "repair session resume",
    )
    assert resumed["session"]["status"] == "active"

    events = require(
        a.request("GET", f"/api/v1/repair-sessions/{session_id}/events?limit=100"),
        200,
        "event history",
    )
    event_types = [row["event_type"] for row in events["items"]]
    required_events = {
        "session_started",
        "storage_location_created",
        "fastener_recorded",
        "inventory_item_recorded",
        "observation_recorded",
        "session_paused",
        "session_resumed",
    }
    assert required_events.issubset(set(event_types))
    sequences = [row["sequence"] for row in events["items"]]
    assert sequences == sorted(sequences) and len(sequences) == len(set(sequences))
    print("PASS ordered event history")

    b = Client()
    registration_b = require(
        b.request(
            "POST",
            "/api/v1/auth/register",
            payload={
                "email": f"qa-partgraph-b-{suffix}@example.com",
                "username": f"qa_prod_b_{suffix}",
                "password": "ProdQa_" + secrets.token_urlsafe(18),
            },
            headers=CSRF,
        ),
        200,
        "owner B registration",
    )
    assert registration_b["user"]["id"] != owner_a
    b_garage = require(b.request("GET", "/api/v1/user-vehicles"), 200, "owner B empty garage")
    assert b_garage == []

    foreign_vehicle = b.request("GET", f"/api/v1/user-vehicles/{vehicle_id}")
    require(foreign_vehicle, 404, "owner B blocked from owner A vehicle")
    assert code(foreign_vehicle) == "USER_VEHICLE_NOT_FOUND"
    foreign_session = b.request("GET", f"/api/v1/repair-sessions/{session_id}/resume")
    require(foreign_session, 404, "owner B blocked from owner A session")
    assert code(foreign_session) == "REPAIR_SESSION_NOT_FOUND"
    foreign_memory = b.request("GET", f"/api/v1/repair-sessions/{session_id}/observations")
    require(foreign_memory, 404, "owner B blocked from owner A repair memory")
    assert code(foreign_memory) == "REPAIR_SESSION_NOT_FOUND"

    archived = require(
        a.request("PATCH", f"/api/v1/repair-sessions/{session_id}/archive", headers=edit_headers(device)),
        200,
        "repair session archive",
    )
    assert archived["session"]["status"] == "archived"
    archived_vehicle = require(
        a.request("PATCH", f"/api/v1/user-vehicles/{vehicle_id}/archive", headers=CSRF),
        200,
        "vehicle archive",
    )
    assert archived_vehicle["archived_at"] is not None

    require(a.request("POST", "/api/v1/auth/logout", headers=CSRF), 204, "owner A logout")
    signed_out = a.request("GET", "/api/v1/auth/me")
    require(signed_out, 401, "owner A logged out")
    assert code(signed_out) in {"AUTH_REQUIRED", "AUTH_SESSION_REVOKED"}
    require(b.request("POST", "/api/v1/auth/logout", headers=CSRF), 204, "owner B logout")

    result = {
        "catalog_empty": catalog_empty,
        "production_cors_ok": prod_cors_ok,
        "owner_state_flow": "pass",
        "cross_owner_isolation": "pass",
        "pause_resume": "pass",
        "repair_memory": "pass",
        "guided_repair": "blocked_by_empty_canonical_catalog" if catalog_empty else "not_exercised",
        "failures": failures,
    }
    print("RESULT " + json.dumps(result, sort_keys=True))
    if failures:
        raise AssertionError("; ".join(failures))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"RESULT FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
