from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, Route, expect, sync_playwright

BASE_URL = os.environ.get("PARTGRAPH_OFFLINE_E2E_URL", "http://127.0.0.1:8000").rstrip("/")
STATE_PATH = Path(
    os.environ.get(
        "PARTGRAPH_OFFLINE_E2E_STATE",
        "/tmp/phase9-offline-guidance.json",
    )
)
USERNAME = "phase9_offline"
EMAIL = "phase9-offline@example.com"
PASSWORD = "Phase9OfflineE2E!2026"
PACK_KEY = "partgraph:offline-repair-pack:v2"
ACTIVE_SESSION_KEY = "partgraph:active-repair-session"
SHELL_CACHE = "partgraph-shell-v2"


def _browser_api(
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


def _stored_pack(page: Page) -> dict[str, Any]:
    raw = page.evaluate("(key) => window.sessionStorage.getItem(key)", PACK_KEY)
    if not raw:
        raise AssertionError("offline repair pack is not cached in sessionStorage")
    pack = json.loads(raw)
    if not isinstance(pack, dict):
        raise AssertionError("offline repair pack is not a JSON object")
    return pack


def _assert_private_pack_minimized(page: Page, pack: dict[str, Any]) -> None:
    for key in ("owner_id", "email", "username"):
        if key in pack:
            raise AssertionError(f"offline repair pack leaked private identity field {key}")
    if pack.get("read_only") is not True:
        raise AssertionError("offline repair pack is not explicitly read-only")
    if page.evaluate("(key) => window.localStorage.getItem(key)", PACK_KEY) is not None:
        raise AssertionError("offline repair pack must not be stored in durable localStorage")


def _assert_shell_cache_has_no_api(page: Page) -> None:
    urls = page.evaluate(
        """
        async (cacheName) => {
          const cache = await caches.open(cacheName);
          return (await cache.keys()).map((request) => request.url);
        }
        """,
        SHELL_CACHE,
    )
    if not any(url.endswith("/index.html") or url.rstrip("/").endswith(":8000") for url in urls):
        raise AssertionError(
            "service-worker shell cache is missing the application document: "
            + ", ".join(urls)
        )
    if any("/api/" in url for url in urls):
        raise AssertionError(
            "service-worker shell cache contains a private API response: "
            + ", ".join(urls)
        )


def _degraded_health(route: Route) -> None:
    route.fulfill(
        status=503,
        headers={
            "Content-Type": "application/json",
            "X-PartGraph-API-Version": "v1",
            "X-Request-ID": "phase9-degraded-health",
        },
        body=json.dumps(
            {
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "Synthetic Phase 9 degraded database state.",
                    "request_id": "phase9-degraded-health",
                    "retryable": False,
                }
            }
        ),
    )


def _trigger_repair_sync(page: Page) -> None:
    page.evaluate(
        """
        window.dispatchEvent(
          new CustomEvent('partgraph:active-repair-session-changed', {
            detail: { sessionId: sessionStorage.getItem('partgraph:active-repair-session') },
          }),
        );
        """
    )


def _assert_offline_workspace(page: Page, pack: dict[str, Any]) -> None:
    expect(page.get_by_text("Offline repair pack · read only", exact=True)).to_be_visible()
    expect(page.get_by_text("OFFLINE PACK · READ ONLY", exact=True)).to_be_visible()
    expect(
        page.get_by_text(f"Definition v{pack['repair_definition_version']}").first
    ).to_be_visible()
    expect(page.get_by_text(pack["pack_version"], exact=True)).to_be_visible()
    expect(page.get_by_text("Last sync", exact=False).first).to_be_visible()

    button_labels = page.get_by_role("button").all_text_contents()
    allowed = {"Overview", "readiness", "guidance", "completion", "Repair log"}
    unexpected = [item.strip() for item in button_labels if item.strip() not in allowed]
    if unexpected:
        raise AssertionError(
            "offline workspace exposed controls outside read-only navigation: "
            + ", ".join(unexpected)
        )


def main() -> None:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    vehicle_selection = state["vehicle_selection"]
    repair_key = state["repair_key"]

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            reduced_motion="reduce",
        )
        page = context.new_page()
        console_errors: list[str] = []
        page_errors: list[str] = []
        page.on(
            "console",
            lambda message: (
                console_errors.append(message.text)
                if message.type == "error"
                else None
            ),
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))

        page.goto(BASE_URL, wait_until="networkidle")
        expect(page.get_by_role("heading", name="Sign in.")).to_be_visible()
        console_errors.clear()
        page_errors.clear()

        page.get_by_role("button", name="Create account").click()
        page.get_by_label("Email").fill(EMAIL)
        page.get_by_label("Username").fill(USERNAME)
        page.get_by_label("Password").fill(PASSWORD)
        page.get_by_role("button", name="Create private workspace").click()
        expect(page.get_by_text(f"@{USERNAME} · {EMAIL}")).to_be_visible()

        vehicle = _require_api(
            _browser_api(
                page,
                "/api/v1/user-vehicles/manual",
                method="POST",
                payload={
                    "nickname": "Phase 9 offline Civic",
                    "selection": vehicle_selection,
                },
                headers={"X-PartGraph-CSRF": "1"},
            ),
            201,
            "manual exact-vehicle creation",
        )

        device_id = page.evaluate("crypto.randomUUID()")
        session = _require_api(
            _browser_api(
                page,
                "/api/v1/repair-sessions",
                method="POST",
                payload={
                    "user_vehicle_id": vehicle["id"],
                    "title": "Phase 9 offline continuity",
                },
                headers={
                    "X-PartGraph-CSRF": "1",
                    "X-PartGraph-Device-ID": device_id,
                    "Idempotency-Key": "phase9_offline_session",
                },
            ),
            201,
            "repair-session creation",
        )
        session_id = session["session"]["id"]

        binding = _require_api(
            _browser_api(
                page,
                f"/api/v1/repair-sessions/{session_id}/repair-definition",
                method="PUT",
                payload={"repair_key": repair_key},
                headers={
                    "X-PartGraph-CSRF": "1",
                    "X-PartGraph-Device-ID": device_id,
                },
            ),
            200,
            "verified repair binding",
        )
        if binding.get("binding_state") != "bound":
            raise AssertionError("repair definition was not bound before offline caching")

        page.evaluate(
            "([key, value]) => sessionStorage.setItem(key, value)",
            [ACTIVE_SESSION_KEY, session_id],
        )
        _trigger_repair_sync(page)
        page.wait_for_function(
            "(key) => sessionStorage.getItem(key) !== null",
            arg=PACK_KEY,
        )

        first_pack = _stored_pack(page)
        _assert_private_pack_minimized(page, first_pack)
        if first_pack.get("session_id") != session_id:
            raise AssertionError("cached offline pack belongs to the wrong repair session")
        if first_pack.get("repair_definition_id") != state["repair_definition_id"]:
            raise AssertionError("cached offline pack belongs to the wrong repair definition")
        if first_pack.get("server_sequence") != session["session"]["current_sequence"]:
            raise AssertionError("offline pack did not preserve the server-confirmed session sequence")

        page.evaluate("window.location.hash = '#/guidance'")
        expect(
            page.get_by_role("heading", name="Focus on what you need to do next.")
        ).to_be_visible()

        page.wait_for_function(
            """
            async (cacheName) => {
              if (!('serviceWorker' in navigator)) return false;
              await navigator.serviceWorker.ready;
              const cache = await caches.open(cacheName);
              const urls = (await cache.keys()).map((request) => request.url);
              return Boolean(navigator.serviceWorker.controller)
                && urls.some((url) => url.includes('/assets/') && url.endsWith('.js'));
            }
            """,
            arg=SHELL_CACHE,
        )
        _assert_shell_cache_has_no_api(page)

        page.route("**/api/v1/health/ready", _degraded_health)
        _trigger_repair_sync(page)
        _assert_offline_workspace(page, first_pack)
        degraded_pack = _stored_pack(page)
        if degraded_pack["generated_at"] != first_pack["generated_at"]:
            raise AssertionError("degraded mode invented a newer offline snapshot")

        page.unroute("**/api/v1/health/ready", _degraded_health)
        _trigger_repair_sync(page)
        expect(page.get_by_text("Offline repair pack · read only", exact=True)).not_to_be_visible()
        expect(
            page.get_by_role("heading", name="Focus on what you need to do next.")
        ).to_be_visible()

        page.wait_for_function(
            "([key, generatedAt]) => JSON.parse(sessionStorage.getItem(key)).generated_at !== generatedAt",
            arg=[PACK_KEY, first_pack["generated_at"]],
        )
        refreshed_pack = _stored_pack(page)
        _assert_private_pack_minimized(page, refreshed_pack)

        context.set_offline(True)
        page.evaluate("window.dispatchEvent(new Event('offline'))")
        _assert_offline_workspace(page, refreshed_pack)
        page.reload(wait_until="domcontentloaded")
        _assert_offline_workspace(page, refreshed_pack)

        reloaded_pack = _stored_pack(page)
        if reloaded_pack["pack_version"] != refreshed_pack["pack_version"]:
            raise AssertionError("offline reload changed the server-confirmed repair-pack version")
        if reloaded_pack["server_sequence"] != refreshed_pack["server_sequence"]:
            raise AssertionError("offline reload changed the server-confirmed sequence")
        if reloaded_pack["generated_at"] != refreshed_pack["generated_at"]:
            raise AssertionError("offline reload invented a newer sync timestamp")
        _assert_shell_cache_has_no_api(page)

        context.set_offline(False)
        page.evaluate("window.dispatchEvent(new Event('online'))")
        expect(page.get_by_text("Offline repair pack · read only", exact=True)).not_to_be_visible()
        expect(page.get_by_text(f"@{USERNAME} · {EMAIL}")).to_be_visible()
        expect(
            page.get_by_role("heading", name="Focus on what you need to do next.")
        ).to_be_visible()

        page.wait_for_function(
            "([key, generatedAt]) => JSON.parse(sessionStorage.getItem(key)).generated_at !== generatedAt",
            arg=[PACK_KEY, refreshed_pack["generated_at"]],
        )

        page.get_by_role("button", name="Sign out").click()
        expect(page.get_by_role("heading", name="Create your account.")).to_be_visible()
        if page.evaluate("(key) => sessionStorage.getItem(key)", PACK_KEY) is not None:
            raise AssertionError("confirmed logout did not clear the private offline repair pack")

        if page_errors:
            raise AssertionError("browser page errors: " + " | ".join(page_errors))
        filtered_console = [
            item
            for item in console_errors
            if "favicon.ico" not in item.lower()
            and "failed to load resource" not in item.lower()
            and "err_internet_disconnected" not in item.lower()
        ]
        if filtered_console:
            raise AssertionError("browser console errors: " + " | ".join(filtered_console))

        context.close()
        browser.close()

    print(
        "Offline/degraded browser acceptance passed: authoritative read-only pack caching, "
        "degraded API fallback, full network-loss continuity, service-worker offline reload, "
        "reconnect refresh, no API response caching, and logout cache clearing."
    )


if __name__ == "__main__":
    main()
