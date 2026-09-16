import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from partgraph import config

REPO_ROOT = Path(__file__).resolve().parents[2]
PARTGRAPH_ROOT = REPO_ROOT / "api" / "partgraph"
SCALE_GATE_DOC = REPO_ROOT / "docs" / "PROVIDER_INGESTION_SCALE_GATE.md"
VERCEL_CONFIG = REPO_ROOT / "api" / "vercel.json"


def _production_callers(symbol: str, *, definition_path: str) -> set[str]:
    callers: set[str] = set()
    for path in PARTGRAPH_ROOT.rglob("*.py"):
        relative = path.relative_to(PARTGRAPH_ROOT).as_posix()
        if relative == definition_path:
            continue
        if f"{symbol}(" in path.read_text(encoding="utf-8"):
            callers.add(relative)
    return callers


class ProviderIngestionScaleGateTests(unittest.TestCase):
    def test_mvp_supports_only_operator_synchronous_ingestion(self) -> None:
        self.assertEqual(config.DEFAULT_PROVIDER_INGESTION_MODE, "operator_sync")
        self.assertEqual(config.SUPPORTED_PROVIDER_INGESTION_MODES, {"operator_sync"})
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PARTGRAPH_PROVIDER_INGESTION_MODE", None)
            self.assertEqual(config._provider_ingestion_mode(), "operator_sync")

    def test_high_volume_modes_fail_closed_at_configuration(self) -> None:
        for mode in ("scheduled", "continuous", "bulk", "worker"):
            with self.subTest(mode=mode):
                with patch.dict(
                    os.environ,
                    {"PARTGRAPH_PROVIDER_INGESTION_MODE": mode},
                    clear=False,
                ):
                    with self.assertRaisesRegex(ValueError, "durable queue/backpressure"):
                        config._provider_ingestion_mode()

    def test_provider_staging_has_only_the_operator_router_as_runtime_caller(self) -> None:
        self.assertEqual(
            _production_callers(
                "stage_nhtsa_recall_query",
                definition_path="operator/nhtsa.py",
            ),
            {"operator/router.py"},
        )
        self.assertEqual(
            _production_callers(
                "stage_reference_parts_dataset",
                definition_path="operator/reference_parts.py",
            ),
            {"operator/router.py"},
        )
        self.assertEqual(
            _production_callers(
                "collect_and_stage_nhtsa_recalls",
                definition_path="knowledge/nhtsa.py",
            ),
            set(),
        )

    def test_vercel_crons_do_not_schedule_provider_ingestion(self) -> None:
        document = json.loads(VERCEL_CONFIG.read_text(encoding="utf-8"))
        cron_paths = [str(item.get("path", "")) for item in document.get("crons", [])]
        for path in cron_paths:
            self.assertNotIn("/operator/nhtsa/", path)
            self.assertNotIn("/operator/reference-parts/", path)

    def test_scale_gate_documents_queue_prerequisites(self) -> None:
        text = SCALE_GATE_DOC.read_text(encoding="utf-8").casefold()
        for required in (
            "durable job record or queue",
            "idempotent",
            "bounded worker concurrency",
            "per-provider rate limits",
            "exponential retry backoff",
            "terminal failure/dead-letter state",
            "operator visibility",
            "load tests",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
