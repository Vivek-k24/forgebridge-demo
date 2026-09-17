from __future__ import annotations

import http.cookiejar
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

BASE_URL = os.environ.get("PARTGRAPH_FULL_STACK_URL", "http://127.0.0.1:8000").rstrip("/")
ORIGIN = BASE_URL
CSRF_HEADER = "X-PartGraph-CSRF"
CSRF_VALUE = "1"
API_VERSION = "v1"


@dataclass(frozen=True)
class Response:
    status: int
    headers: Any
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


def _opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def _request(
    opener: urllib.request.OpenerDirector,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    csrf: bool = False,
) -> Response:
    data = None
    headers = {"Origin": ORIGIN}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if csrf:
        headers[CSRF_HEADER] = CSRF_VALUE

    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with opener.open(request, timeout=10) as response:
            return Response(
                status=response.status,
                headers=response.headers,
                body=response.read(),
            )
    except urllib.error.HTTPError as exc:
        return Response(
            status=exc.code,
            headers=exc.headers,
            body=exc.read(),
        )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _require_api_version(response: Response) -> None:
    _require(
        response.headers.get("X-PartGraph-API-Version") == API_VERSION,
        f"expected X-PartGraph-API-Version={API_VERSION!r}",
    )


def main() -> None:
    opener = _opener()

    index = _request(opener, "/")
    _require(index.status == 200, f"frontend index returned {index.status}")
    html = index.body.decode("utf-8")
    _require('id="root"' in html, "frontend root mount is missing")
    asset_match = re.search(r'<script[^>]+src="([^"]+\.js)"', html)
    _require(asset_match is not None, "built frontend JavaScript asset is missing")
    asset_path = asset_match.group(1)

    asset = _request(opener, asset_path)
    _require(asset.status == 200, f"frontend asset returned {asset.status}")
    _require(len(asset.body) > 1000, "frontend JavaScript asset is unexpectedly small")

    ready = _request(opener, "/api/v1/health/ready")
    _require(ready.status == 200, f"readiness returned {ready.status}")
    _require_api_version(ready)
    ready_payload = ready.json()
    _require(ready_payload.get("status") == "ready", "API is not ready")
    _require(ready_payload.get("database") == "ready", "database is not ready")

    registration = _request(
        opener,
        "/api/v1/auth/register",
        method="POST",
        csrf=True,
        payload={
            "email": "phase9-full-stack@example.com",
            "username": "phase9_full_stack",
            "password": "Phase9FullStack!2026",
        },
    )
    _require(registration.status == 200, f"registration returned {registration.status}")
    _require_api_version(registration)
    registration_payload = registration.json()
    user = registration_payload.get("user", {})
    _require(user.get("username") == "phase9_full_stack", "registered username mismatch")
    set_cookie = registration.headers.get("Set-Cookie", "")
    _require("partgraph_session=" in set_cookie, "session cookie was not issued")
    _require("HttpOnly" in set_cookie, "session cookie is not HttpOnly")

    me = _request(opener, "/api/v1/auth/me")
    _require(me.status == 200, f"authenticated session check returned {me.status}")
    _require(me.json().get("user", {}).get("username") == "phase9_full_stack", "session user mismatch")

    preference_update = _request(
        opener,
        "/api/v1/account/preferences",
        method="PATCH",
        csrf=True,
        payload={"units": "metric"},
    )
    _require(preference_update.status == 200, f"preference update returned {preference_update.status}")
    _require(preference_update.json().get("units") == "metric", "preference update did not persist")

    preference_read = _request(opener, "/api/v1/account/preferences")
    _require(preference_read.status == 200, f"preference read returned {preference_read.status}")
    _require(preference_read.json().get("units") == "metric", "persisted preference mismatch")

    vehicle_create = _request(
        opener,
        "/api/v1/user-vehicles/manual",
        method="POST",
        csrf=True,
        payload={
            "nickname": "Phase 9 integration vehicle",
            "selection": {
                "year": 2009,
                "market": "US",
                "make": "Synthetic",
                "model": "Full Stack Fixture",
                "trim": "CI-only",
            },
        },
    )
    _require(vehicle_create.status == 201, f"Garage vehicle create returned {vehicle_create.status}")
    vehicle = vehicle_create.json()
    _require(vehicle.get("nickname") == "Phase 9 integration vehicle", "Garage nickname mismatch")
    _require(vehicle.get("identity_source") == "manual", "Garage identity source mismatch")

    vehicles = _request(opener, "/api/v1/user-vehicles")
    _require(vehicles.status == 200, f"Garage list returned {vehicles.status}")
    vehicle_rows = vehicles.json()
    _require(len(vehicle_rows) == 1, f"expected one Garage vehicle, got {len(vehicle_rows)}")
    _require(vehicle_rows[0].get("id") == vehicle.get("id"), "Garage read-after-write mismatch")

    logout = _request(
        opener,
        "/api/v1/auth/logout",
        method="POST",
        csrf=True,
    )
    _require(logout.status == 204, f"logout returned {logout.status}")

    after_logout = _request(opener, "/api/v1/auth/me")
    _require(after_logout.status == 401, f"revoked session returned {after_logout.status}")
    error = after_logout.json().get("error", {})
    _require(
        error.get("code") in {"AUTH_REQUIRED", "AUTH_SESSION_REVOKED", "AUTH_SESSION_EXPIRED"},
        f"unexpected post-logout error code: {error.get('code')}",
    )

    print(
        "Full-stack integration passed: built web asset + FastAPI + migrated PostgreSQL + "
        "auth/session + preferences + Garage persistence + logout."
    )


if __name__ == "__main__":
    main()
