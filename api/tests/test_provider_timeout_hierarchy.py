import os
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from partgraph.config import MAX_REQUEST_DEADLINE_SECONDS, _load_settings, settings
from partgraph.knowledge.nhtsa import NhtsaRecallCollector

WEB_API_SOURCE = Path(__file__).resolve().parents[2] / "web" / "src" / "api.ts"


def _browser_timeout_seconds() -> float:
    source = WEB_API_SOURCE.read_text(encoding="utf-8")
    match = re.search(r"const HARD_TIMEOUT_MS = ([0-9_]+)", source)
    if match is None:
        raise AssertionError("Browser hard timeout constant was not found")
    return int(match.group(1).replace("_", "")) / 1000


class ProviderTimeoutHierarchyTests(unittest.TestCase):
    def test_default_budgets_preserve_provider_api_browser_order(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            configured = _load_settings()
        browser_timeout = _browser_timeout_seconds()

        self.assertLess(configured.nhtsa_timeout_seconds, configured.request_deadline_seconds)
        self.assertLess(configured.request_deadline_seconds, browser_timeout)

    def test_recall_collector_uses_shared_nhtsa_timeout_budget(self) -> None:
        collector = NhtsaRecallCollector()
        self.assertEqual(collector.timeout_seconds, settings.nhtsa_timeout_seconds)
        self.assertLess(collector.timeout_seconds, settings.request_deadline_seconds)

    def test_recall_collector_cannot_loosen_configured_provider_budget(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            NhtsaRecallCollector(timeout_seconds=settings.nhtsa_timeout_seconds + 0.1)

    def test_environment_override_without_deadline_reserve_fails_closed(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PARTGRAPH_NHTSA_TIMEOUT_SECONDS": "7.5",
                "PARTGRAPH_REQUEST_DEADLINE_SECONDS": "8.0",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "provider/API deadline reserve"):
                _load_settings()

    def test_valid_override_keeps_one_second_reserve_on_normal_deadline(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PARTGRAPH_NHTSA_TIMEOUT_SECONDS": "7.0",
                "PARTGRAPH_REQUEST_DEADLINE_SECONDS": "8.0",
            },
            clear=True,
        ):
            configured = _load_settings()
        self.assertEqual(configured.nhtsa_timeout_seconds, 7.0)
        self.assertEqual(configured.request_deadline_seconds, 8.0)

    def test_all_permitted_api_deadlines_are_below_browser_hard_timeout(self) -> None:
        self.assertLess(MAX_REQUEST_DEADLINE_SECONDS, _browser_timeout_seconds())


if __name__ == "__main__":
    unittest.main()
