from __future__ import annotations

import sys
from uuid import uuid4

import httpx

API_URL = "http://api:8000"
ORIGIN = "http://localhost:15173"
PASSWORD = "correct-horse-battery-staple"
VALID_VIN = "1HGCM82633A004352"


def headers() -> dict[str, str]:
    return {"X-PartGraph-CSRF": "1", "Origin": ORIGIN}


def body(response: httpx.Response):
    try:
        return response.json()
    except Exception:
        return response.text


def require(response: httpx.Response, status: int, label: str):
    if response.status_code != status:
        raise AssertionError(
            f"{label}: expected HTTP {status}, got {response.status_code}: {body(response)}"
        )
    return body(response)


def require_error(response: httpx.Response, status: int, code: str, label: str) -> None:
    payload = require(response, status, label)
    actual = payload.get("error", {}).get("code") if isinstance(payload, dict) else None
    if actual != code:
        raise AssertionError(f"{label}: expected {code}, got {actual}: {payload}")


def main() -> int:
    suffix = uuid4().hex[:10]
    email = f"platform-{suffix}@example.com"
    username = f"platform_{suffix}"
    checks: list[str] = []

    try:
        with httpx.Client(base_url=API_URL, timeout=10.0) as client:
            ready = require(client.get("/api/v1/health/ready"), 200, "API readiness")
            if ready.get("status") != "ready":
                raise AssertionError(f"API readiness payload unexpected: {ready}")
            checks.append("health/readiness")

            brands = require(client.get("/api/v1/vehicle-brands"), 200, "supported brands")
            names = {item["name"] for item in brands}
            if len(names) != 31 or not {"Honda", "Toyota", "Ford", "Volvo", "Suzuki"}.issubset(names):
                raise AssertionError(f"supported brand policy unexpected: {sorted(names)}")
            checks.append("supported/legacy brand policy")

            selection = require(
                client.post(
                    "/api/v1/vehicle-selection/resolve",
                    json={
                        "year": 2012,
                        "market": "US",
                        "make": "Toyota",
                        "model": "Acceptance Selector",
                        "trim": "Test Trim",
                        "body_style": "Sedan",
                        "engine": "2.5L I4",
                        "transmission": "Automatic",
                        "drivetrain": "FWD",
                    },
                ),
                200,
                "vehicle selection normalization",
            )
            if selection["normalized"]["make"] != "Toyota":
                raise AssertionError(f"vehicle make did not normalize: {selection}")
            checks.append("vehicle selector normalization")

            excluded = client.post(
                "/api/v1/vehicle-selection/resolve",
                json={
                    "year": 2024,
                    "market": "US",
                    "make": "Tesla",
                    "model": "Model 3",
                },
            )
            if excluded.status_code != 422:
                raise AssertionError(
                    f"excluded-brand boundary expected 422, got {excluded.status_code}: {body(excluded)}"
                )
            checks.append("excluded-brand policy boundary")

            registered = require(
                client.post(
                    "/api/v1/auth/register",
                    json={"email": email, "username": username, "password": PASSWORD},
                    headers=headers(),
                ),
                200,
                "register",
            )
            user_id = registered["user"]["id"]
            checks.append("register + session cookie")

            me = require(client.get("/api/v1/auth/me"), 200, "auth me")
            if me["user"]["id"] != user_id:
                raise AssertionError("auth/me returned the wrong user")
            checks.append("authenticated session read")

            preference = require(
                client.patch(
                    "/api/v1/account/preferences",
                    json={"units": "metric"},
                    headers=headers(),
                ),
                200,
                "update preferences",
            )
            if preference["units"] != "metric":
                raise AssertionError(f"preference update not persisted: {preference}")
            checks.append("account preferences")

            provider = require(
                client.post(
                    "/api/v1/user-vehicles/vin/decode",
                    json={"market": "US", "vin": VALID_VIN},
                    headers=headers(),
                ),
                200,
                "VIN provider decode",
            )
            if provider["source"] != "provider" or provider["provider"] != "nhtsa_vpic":
                raise AssertionError(f"first VIN decode did not use provider: {provider}")
            checks.append("VIN provider adapter")

            cached = require(
                client.post(
                    "/api/v1/user-vehicles/vin/decode",
                    json={"market": "US", "vin": VALID_VIN},
                    headers=headers(),
                ),
                200,
                "VIN cache decode",
            )
            if cached["source"] != "cache":
                raise AssertionError(f"second VIN decode did not use owner cache: {cached}")
            checks.append("VIN owner cache")

            vin_vehicle = require(
                client.post(
                    "/api/v1/user-vehicles/vin",
                    json={"market": "US", "vin": VALID_VIN, "nickname": "Acceptance VIN"},
                    headers=headers(),
                ),
                201,
                "save VIN vehicle",
            )
            if vin_vehicle["identity_source"] != "vin":
                raise AssertionError(f"VIN vehicle source unexpected: {vin_vehicle}")
            if vin_vehicle["masked_vin"] != "***********004352":
                raise AssertionError(f"VIN masking unexpected: {vin_vehicle['masked_vin']}")
            checks.append("encrypted VIN vehicle save + masking")

            duplicate = client.post(
                "/api/v1/user-vehicles/vin",
                json={"market": "US", "vin": VALID_VIN, "nickname": "Duplicate"},
                headers=headers(),
            )
            require_error(duplicate, 409, "USER_VEHICLE_VIN_EXISTS", "duplicate owner VIN")
            checks.append("VIN duplicate protection")

            invalid_vin = client.post(
                "/api/v1/user-vehicles/vin/decode",
                json={"market": "US", "vin": "1HGCM82633A004351"},
                headers=headers(),
            )
            require_error(invalid_vin, 422, "VIN_CHECK_DIGIT_INVALID", "VIN check digit")
            checks.append("VIN syntax/check-digit validation")

            archived = require(
                client.patch(
                    f"/api/v1/user-vehicles/{vin_vehicle['id']}/archive",
                    headers=headers(),
                ),
                200,
                "archive vehicle",
            )
            if archived["archived_at"] is None:
                raise AssertionError("vehicle archive timestamp missing")
            active = require(client.get("/api/v1/user-vehicles"), 200, "active vehicle list")
            if any(item["id"] == vin_vehicle["id"] for item in active):
                raise AssertionError("archived vehicle remained in active list")
            all_vehicles = require(
                client.get("/api/v1/user-vehicles?include_archived=true"),
                200,
                "archived vehicle list",
            )
            if not any(item["id"] == vin_vehicle["id"] for item in all_vehicles):
                raise AssertionError("archived vehicle missing from full list")
            checks.append("UserVehicle archive/list behavior")

            require(client.post("/api/v1/auth/logout", headers=headers()), 204, "logout")
            require_error(client.get("/api/v1/auth/me"), 401, "AUTH_REQUIRED", "revoked session")
            checks.append("logout/session revocation")

            logged_in = require(
                client.post(
                    "/api/v1/auth/login",
                    json={"identifier": username, "password": PASSWORD},
                    headers=headers(),
                ),
                200,
                "login",
            )
            if logged_in["user"]["id"] != user_id:
                raise AssertionError("login resolved a different user")
            checks.append("login by username")

        print("Platform/VIN acceptance probes")
        for check in checks:
            print(f"  PASS  {check}")
        print(f"RESULT: PASS — {len(checks)} platform/VIN probes passed.")
        return 0
    except Exception as exc:
        print("Platform/VIN acceptance probes")
        for check in checks:
            print(f"  PASS  {check}")
        print(f"  FAIL  {type(exc).__name__}: {exc}")
        print("RESULT: FAIL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
