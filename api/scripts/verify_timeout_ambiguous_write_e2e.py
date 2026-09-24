from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, Route, expect, sync_playwright

BASE_URL = os.environ.get(
    "PARTGRAPH_TIMEOUT_RECOVERY_URL",
    "http://127.0.0.1:8000",
).rstrip("/")
STATE_PATH = Path(
    os.environ.get(
        "PARTGRAPH_TIMEOUT_RECOVERY_STATE",
        "/tmp/phase9-timeout-recovery.json",
    )
)
USERNAME = "phase9_timeout_recovery"
EMAIL = "phase9-timeout-recovery@example.com"
PASSWORD = "Phase9TimeoutRecovery!2026"
ACTIVE_SESSION_KEY = "partgraph:active-repair-session"


def _api(
    page: Page,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    return page.evaluate(
        """
        async ({ path, method, payload, headers }) => {
          const requestHeaders = { ...(headers || {}) };
          let body;
          if (payload !== null) {
            requestHeaders['Content-Type'] = 'application/json';
            body = JSON.stringify(payload);
          }
          const response = await fetch(path, {
            method,
            credentials: 'include',
            headers: requestHeaders,
            body,
          });
          const text = await response.text();
          let parsed = null;
          if (text) {
            try { parsed = JSON.parse(text); } catch { parsed = text; }
          }
          return {
            status: response.status,
            body: parsed,
            apiVersion: response.headers.get('x-partgraph-api-version'),
          };
        }
        """,
        {
            "path": path,
            "method": method,
            "payload": payload,
            "headers": headers or {},
        },
    )


def _require_api(response: dict[str, Any], status: int, label: str) -> dict[str, Any]:
    if response["status"] != status:
        raise AssertionError(
            f"{label} returned HTTP {response['status']}: {response['body']}"
        )
    if response["apiVersion"] != "v1":
        raise AssertionError(f"{label} returned the wrong API version")
    body = response["body"]
    if not isinstance(body, dict):
        raise AssertionError(f"{label} did not return a JSON object")
    return body


def _device_id(page: Page) -> str:
    return page.evaluate(
        """
        () => {
          const key = 'partgraph.device-id';
          const existing = localStorage.getItem(key);
          if (existing) return existing;
          const created = crypto.randomUUID();
          localStorage.setItem(key, created);
          return created;
        }
        """
    )


def _idempotency_key(route: Route) -> str:
    key = route.request.headers.get("idempotency-key")
    if not key:
        raise AssertionError("repair mutation did not carry an idempotency key")
    return key


def main() -> None:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    vehicle_selection = state["vehicle_selection"]

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            reduced_motion="reduce",
        )
        page = context.new_page()

        page.goto(BASE_URL, wait_until="networkidle")
        expect(page.get_by_role("heading", name="Sign in.")).to_be_visible()

        page.get_by_role("button", name="Create account").click()
        page.get_by_label("Email").fill(EMAIL)
        page.get_by_label("Username").fill(USERNAME)
        page.get_by_label("Password", exact=True).fill(PASSWORD)
        page.get_by_role("button", name="Create private workspace").click()
        expect(page.get_by_text(f"@{USERNAME} · {EMAIL}")).to_be_visible()

        vehicle = _require_api(
            _api(
                page,
                "/api/v1/user-vehicles/manual",
                method="POST",
                payload={
                    "nickname": "Phase 9 recovery vehicle",
                    "selection": vehicle_selection,
                },
                headers={"X-PartGraph-CSRF": "1"},
            ),
            201,
            "vehicle creation",
        )

        device_id = _device_id(page)
        created = _require_api(
            _api(
                page,
                "/api/v1/repair-sessions",
                method="POST",
                payload={
                    "user_vehicle_id": vehicle["id"],
                    "title": "Phase 9 ambiguous write recovery",
                },
                headers={
                    "X-PartGraph-CSRF": "1",
                    "X-PartGraph-Device-ID": device_id,
                    "Idempotency-Key": "phase9_recovery_session",
                },
            ),
            201,
            "repair session creation",
        )
        session_id = created["session"]["id"]

        page.evaluate(
            "([key, value]) => sessionStorage.setItem(key, value)",
            [ACTIVE_SESSION_KEY, session_id],
        )
        page.evaluate("window.location.hash = '#/resume'")
        expect(
            page.get_by_role(
                "heading",
                name="Pick up the repair without rebuilding the story in your head.",
            )
        ).to_be_visible()
        expect(page.get_by_role("button", name="Pause repair")).to_be_enabled()

        recovery_urls: list[str] = []
        page.on(
            "request",
            lambda request: (
                recovery_urls.append(request.url)
                if "/api/v1/repair-recovery/" in request.url
                else None
            ),
        )

        pause_keys: list[str] = []
        pause_network_calls = 0

        def lose_committed_pause(route: Route) -> None:
            nonlocal pause_network_calls
            pause_network_calls += 1
            pause_keys.append(_idempotency_key(route))
            response = route.fetch()
            if response.status != 200:
                raise AssertionError(
                    f"server pause mutation returned HTTP {response.status}"
                )
            route.abort("failed")

        pause_pattern = f"**/api/v1/repair-sessions/{session_id}/pause"
        page.route(pause_pattern, lose_committed_pause)
        page.get_by_role("button", name="Pause repair").click()
        expect(page.get_by_role("button", name="Resume repair")).to_be_visible(
            timeout=10_000
        )
        page.unroute(pause_pattern, lose_committed_pause)

        if pause_network_calls != 1:
            raise AssertionError(
                f"ambiguous committed pause was sent {pause_network_calls} times"
            )
        if len(pause_keys) != 1:
            raise AssertionError("pause mutation did not expose exactly one idempotency key")
        pause_key = pause_keys[0]
        if not any(
            f"/repair-recovery/sessions/{session_id}/mutations/{pause_key}" in url
            for url in recovery_urls
        ):
            raise AssertionError(
                "browser did not reconcile the lost pause response by idempotency key"
            )

        paused = _require_api(
            _api(
                page,
                f"/api/v1/repair-sessions/{session_id}/resume",
                headers={"X-PartGraph-Device-ID": device_id},
            ),
            200,
            "paused authoritative state",
        )
        if paused["session"]["status"] != "paused":
            raise AssertionError("recovered committed pause is not authoritative server state")

        resume_keys: list[str] = []
        resume_attempts = 0

        def timeout_before_resume_reaches_server(route: Route) -> None:
            nonlocal resume_attempts
            resume_attempts += 1
            resume_keys.append(_idempotency_key(route))
            route.fulfill(
                status=504,
                headers={
                    "Content-Type": "application/json",
                    "X-PartGraph-API-Version": "v1",
                    "X-Request-ID": "phase9_timeout_resume",
                    "Retry-After": "1",
                },
                body=json.dumps(
                    {
                        "error": {
                            "code": "REQUEST_DEADLINE_EXCEEDED",
                            "message": "Synthetic Phase 9 server deadline.",
                            "request_id": "phase9_timeout_resume",
                            "retryable": True,
                            "details": {"deadline_seconds": 8.0},
                        }
                    }
                ),
            )

        resume_pattern = f"**/api/v1/repair-sessions/{session_id}/resume"
        page.route(resume_pattern, timeout_before_resume_reaches_server)
        recovery_count_before = len(recovery_urls)
        page.get_by_role("button", name="Resume repair").click()
        expect(
            page.locator(".workspace-alert--error").filter(
                has_text=re.compile(r"CLIENT_WRITE_STATE_UNCERTAIN")
            ).first
        ).to_be_visible(timeout=10_000)
        page.unroute(resume_pattern, timeout_before_resume_reaches_server)

        if resume_attempts != 1:
            raise AssertionError(
                f"timed-out resume mutation was blindly retried {resume_attempts} times"
            )
        if len(resume_keys) != 1:
            raise AssertionError("resume mutation did not expose exactly one idempotency key")
        resume_key = resume_keys[0]
        new_recovery_urls = recovery_urls[recovery_count_before:]
        if not any(
            f"/repair-recovery/sessions/{session_id}/mutations/{resume_key}" in url
            for url in new_recovery_urls
        ):
            raise AssertionError(
                "browser did not query authoritative state after the resume timeout"
            )

        expect(page.get_by_role("button", name="Resume repair")).to_be_visible()
        authoritative = _require_api(
            _api(
                page,
                f"/api/v1/repair-sessions/{session_id}/resume",
                headers={"X-PartGraph-Device-ID": device_id},
            ),
            200,
            "post-timeout authoritative state",
        )
        if authoritative["session"]["status"] != "paused":
            raise AssertionError(
                "PartGraph changed server state after an unconfirmed timed-out write"
            )

        context.close()
        browser.close()

    print(
        "Timeout/ambiguous-write browser acceptance passed: a committed write with a "
        "lost response recovered by idempotency key; a deadline response triggered "
        "authoritative recovery, no blind mutation retry, explicit uncertain state, "
        "and unchanged server truth."
    )


if __name__ == "__main__":
    main()
