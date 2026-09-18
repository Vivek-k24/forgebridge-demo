from __future__ import annotations

import os
import re

from playwright.sync_api import Page, expect, sync_playwright

BASE_URL = os.environ.get("PARTGRAPH_BROWSER_E2E_URL", "http://127.0.0.1:8000").rstrip("/")
USERNAME = "phase9_browser"
EMAIL = "phase9-browser@example.com"
PASSWORD = "Phase9BrowserE2E!2026"


def _assert_clean_browser(page: Page, console_errors: list[str], page_errors: list[str]) -> None:
    if page_errors:
        raise AssertionError("browser page errors: " + " | ".join(page_errors))
    filtered = [
        item
        for item in console_errors
        if "favicon.ico" not in item.lower()
    ]
    if filtered:
        raise AssertionError("browser console errors: " + " | ".join(filtered))


def main() -> None:
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

        page.get_by_role("button", name="Create account").click()
        expect(page.get_by_role("heading", name="Create your account.")).to_be_visible()

        page.get_by_label("Email").fill(EMAIL)
        page.get_by_label("Username").fill(USERNAME)
        page.get_by_label("Password").fill(PASSWORD)
        page.get_by_role("button", name="Create private workspace").click()

        expect(page.get_by_text(f"@{USERNAME} · {EMAIL}")).to_be_visible()
        expect(
            page.get_by_role(
                "heading",
                name="Your vehicles and repairs, in one place.",
            )
        ).to_be_visible()
        expect(page).to_have_title(re.compile(r"Home \| PartGraph$"))

        page.get_by_role("button", name="Settings").click()
        expect(
            page.get_by_role("heading", name="Account and display settings")
        ).to_be_visible()
        expect(page).to_have_title(re.compile(r"Settings \| PartGraph$"))

        metric = page.get_by_role("radio", name=re.compile(r"^Metric"))
        page.locator("label.settings-choice", has_text="Metric").click()
        expect(metric).to_be_checked()
        expect(
            page.locator("#partgraph-main-content").get_by_text(
                "Measurement units changed to Metric."
            )
        ).to_be_visible()

        page.get_by_role("button", name="Garage").click()
        expect(
            page.get_by_role(
                "heading",
                name=re.compile(r"^Add your vehicle first\."),
            )
        ).to_be_visible()
        expect(page.get_by_role("group", name="Add vehicle method")).to_be_visible()
        expect(
            page.get_by_role("spinbutton", name=re.compile(r"^Model year"))
        ).to_be_visible()
        expect(page.get_by_role("combobox", name="Make", exact=True)).to_be_visible()
        expect(page.get_by_role("combobox", name="Model", exact=True)).to_be_visible()
        expect(page).to_have_title(re.compile(r"Garage \| PartGraph$"))

        page.get_by_role("button", name="Sign out").click()
        expect(page.get_by_role("heading", name="Sign in.")).to_be_visible()

        page.get_by_label("Username or email").fill(USERNAME)
        page.get_by_label("Password").fill(PASSWORD)
        page.get_by_role("button", name="Enter PartGraph").click()

        expect(page.get_by_text(f"@{USERNAME} · {EMAIL}")).to_be_visible()
        units = page.get_by_label("Measurement units")
        expect(units).to_have_value("metric")

        page.get_by_role("button", name="Settings").click()
        expect(page.get_by_role("radio", name=re.compile(r"^Metric"))).to_be_checked()

        focused = page.evaluate("document.activeElement?.textContent || ''")
        if "Account and display settings" not in focused:
            raise AssertionError(
                "SPA navigation did not move browser focus to the destination heading"
            )

        _assert_clean_browser(page, console_errors, page_errors)
        context.close()
        browser.close()

    print(
        "Browser E2E passed: real Chromium registration, SPA navigation/focus, "
        "settings persistence, Garage rendering, logout, and cookie-backed re-login."
    )


if __name__ == "__main__":
    main()
