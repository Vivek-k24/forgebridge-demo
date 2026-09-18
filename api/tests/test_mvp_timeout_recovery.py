from __future__ import annotations

import asyncio
import json
import unittest
from dataclasses import replace

from starlette.requests import Request
from starlette.responses import Response
from unittest.mock import patch

from partgraph.config import settings
from partgraph.main import platform_boundary


def _request() -> Request:
    path = "/api/v1/phase9-deadline-proof"
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "scheme": "https",
            "method": "GET",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [(b"x-request-id", b"phase9_deadline_proof")],
            "client": ("127.0.0.1", 12345),
            "server": ("partgraph.test", 443),
        }
    )


class MvpTimeoutRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_platform_deadline_fails_with_structured_retryable_504(self) -> None:
        configured = replace(settings, request_deadline_seconds=0.01)

        async def slow_handler(_request: Request) -> Response:
            await asyncio.sleep(0.05)
            return Response("late")

        with patch("partgraph.main.settings", configured):
            response = await platform_boundary(_request(), slow_handler)

        self.assertEqual(response.status_code, 504)
        payload = json.loads(response.body)
        self.assertEqual(payload["error"]["code"], "REQUEST_DEADLINE_EXCEEDED")
        self.assertTrue(payload["error"]["retryable"])
        self.assertEqual(payload["error"]["request_id"], "phase9_deadline_proof")
        self.assertEqual(payload["error"]["details"]["deadline_seconds"], 0.01)
        self.assertEqual(response.headers["Retry-After"], "1")
        self.assertEqual(response.headers["X-PartGraph-API-Version"], "v1")
        self.assertEqual(response.headers["X-Request-ID"], "phase9_deadline_proof")


if __name__ == "__main__":
    unittest.main()
