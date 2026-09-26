import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from partgraph.identity.auth.dependencies import current_user, get_auth_session
from partgraph.main import app


class FinalMvpApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.user_id = uuid4()

        async def current_user_override():
            return SimpleNamespace(id=self.user_id)

        async def auth_session_override():
            yield SimpleNamespace()

        app.dependency_overrides[current_user] = current_user_override
        app.dependency_overrides[get_auth_session] = auth_session_override
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()

    def test_live_health_preserves_platform_http_contract(self) -> None:
        request_id = "phase9_api_live_01"
        response = self.client.get(
            "/api/v1/health/live",
            headers={"X-Request-ID": request_id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"service": "partgraph-api", "status": "ok"})
        self.assertEqual(response.headers["x-request-id"], request_id)
        self.assertEqual(response.headers["x-partgraph-api-version"], "v1")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")
        self.assertEqual(response.headers["cache-control"], "no-cache")
        self.assertTrue(response.headers["traceparent"].startswith("00-"))

    def test_ready_health_reaches_migrated_database(self) -> None:
        response = self.client.get("/api/v1/health/ready")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["service"], "partgraph-api")
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["database"], "ready")
        self.assertGreaterEqual(payload["database_ms"], 0)

    def test_unknown_api_route_uses_standard_error_envelope(self) -> None:
        request_id = "phase9_api_missing_01"
        response = self.client.get(
            "/api/v1/does-not-exist",
            headers={"X-Request-ID": request_id},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {
                "error": {
                    "code": "REQUEST_NOT_FOUND",
                    "message": "Not Found",
                    "request_id": request_id,
                    "retryable": False,
                }
            },
        )
        self.assertEqual(response.headers["x-request-id"], request_id)
        self.assertEqual(response.headers["x-partgraph-api-version"], "v1")

    def test_wrong_method_uses_standard_error_envelope(self) -> None:
        response = self.client.post("/api/v1/health/live")

        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json()["error"]["code"], "REQUEST_METHOD_NOT_ALLOWED")
        self.assertEqual(response.json()["error"]["message"], "Method Not Allowed")
        self.assertEqual(response.json()["error"]["request_id"], response.headers["x-request-id"])

    def test_user_vehicle_payload_limit_is_enforced_before_route_execution(self) -> None:
        response = self.client.post(
            "/api/v1/user-vehicles/manual",
            content=b"x" * (32 * 1024 + 1),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["error"]["code"], "REQUEST_PAYLOAD_TOO_LARGE")
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_authenticated_collection_routes_cross_http_boundary(self) -> None:
        with (
            patch(
                "partgraph.identity.user_vehicle.router.list_user_vehicles",
                new=AsyncMock(return_value=[]),
            ) as list_vehicles,
            patch(
                "partgraph.repair_experience.router.list_repair_sessions",
                new=AsyncMock(return_value=[]),
            ) as list_sessions,
        ):
            vehicles = self.client.get("/api/v1/user-vehicles?limit=7")
            sessions = self.client.get("/api/v1/repair-sessions?limit=9")

        self.assertEqual(vehicles.status_code, 200)
        self.assertEqual(vehicles.json(), [])
        self.assertEqual(vehicles.headers["cache-control"], "no-store")
        list_vehicles.assert_awaited_once()
        vehicle_call = list_vehicles.await_args
        self.assertEqual(vehicle_call.kwargs["user_id"], self.user_id)
        self.assertEqual(vehicle_call.kwargs["limit"], 7)

        self.assertEqual(sessions.status_code, 200)
        self.assertEqual(sessions.json(), [])
        self.assertEqual(sessions.headers["cache-control"], "no-store")
        list_sessions.assert_awaited_once()
        session_call = list_sessions.await_args
        self.assertEqual(session_call.kwargs["user_id"], self.user_id)
        self.assertEqual(session_call.kwargs["limit"], 9)

    def test_openapi_exposes_core_mvp_repair_surface(self) -> None:
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]

        expected_methods = {
            "/api/v1/health/live": "get",
            "/api/v1/health/ready": "get",
            "/api/v1/user-vehicles": "get",
            "/api/v1/user-vehicles/manual": "post",
            "/api/v1/repair-sessions": "post",
            "/api/v1/repair-sessions/{session_id}/resume": "get",
            "/api/v1/repair-sessions/{session_id}/offline-pack": "get",
            "/api/v1/repair-sessions/{session_id}/readiness": "get",
            "/api/v1/repair-sessions/{session_id}/guidance": "get",
            "/api/v1/repair-sessions/{session_id}/guidance/plan": "get",
            "/api/v1/repair-sessions/{session_id}/completion": "get",
        }
        for path, method in expected_methods.items():
            with self.subTest(path=path, method=method):
                self.assertIn(path, paths)
                self.assertIn(method, paths[path])


if __name__ == "__main__":
    unittest.main()
