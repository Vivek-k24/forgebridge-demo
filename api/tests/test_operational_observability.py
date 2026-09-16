import json
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from partgraph.observability import (
    OBSERVABILITY_SCHEMA,
    SERVICE_NAME,
    build_event,
    is_mutation_method,
    trace_context_from_header,
)


ROOT = Path(__file__).resolve().parents[2]
SLO_PATH = ROOT / "ops" / "observability" / "slo_v1.json"
RUNBOOK_PATH = ROOT / "docs" / "OPERATIONAL_OBSERVABILITY_RUNBOOK.md"
MAIN_PATH = ROOT / "api" / "partgraph" / "main.py"
DATABASE_PATH = ROOT / "api" / "partgraph" / "database.py"
NHTSA_PATH = ROOT / "api" / "partgraph" / "operator" / "nhtsa.py"
REFERENCE_PARTS_PATH = ROOT / "api" / "partgraph" / "operator" / "reference_parts.py"
PHOTO_LIFECYCLE_PATH = (
    ROOT / "api" / "partgraph" / "repair_experience" / "memory" / "photo_lifecycle.py"
)
TRACE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
SPAN_ID_PATTERN = re.compile(r"^[0-9a-f]{16}$")


class OperationalObservabilityTest(unittest.TestCase):
    def test_valid_w3c_traceparent_preserves_trace_and_creates_local_span(self) -> None:
        header = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        context = trace_context_from_header(header)

        self.assertEqual(context.trace_id, "4bf92f3577b34da6a3ce929d0e0e4736")
        self.assertEqual(context.trace_flags, "01")
        self.assertRegex(context.span_id, SPAN_ID_PATTERN)
        self.assertNotEqual(context.span_id, "00f067aa0ba902b7")
        self.assertEqual(
            context.traceparent,
            f"00-{context.trace_id}-{context.span_id}-01",
        )

    def test_invalid_traceparent_fails_closed_to_new_trace_context(self) -> None:
        context = trace_context_from_header(
            "00-00000000000000000000000000000000-0000000000000000-01"
        )

        self.assertRegex(context.trace_id, TRACE_ID_PATTERN)
        self.assertRegex(context.span_id, SPAN_ID_PATTERN)
        self.assertNotEqual(context.trace_id, "0" * 32)
        self.assertNotEqual(context.span_id, "0" * 16)

    def test_structured_event_has_stable_correlation_fields(self) -> None:
        context = trace_context_from_header(None)
        with patch.dict(
            "os.environ",
            {
                "VERCEL_ENV": "preview",
                "VERCEL_GIT_COMMIT_SHA": "abc123",
            },
            clear=False,
        ):
            payload = build_event(
                "test.signal",
                request_id="request_12345678",
                trace_context=context,
                attributes={"outcome": "success", "count": 2},
            )

        self.assertEqual(payload["schema"], OBSERVABILITY_SCHEMA)
        self.assertEqual(payload["service.name"], SERVICE_NAME)
        self.assertEqual(payload["deployment.environment"], "preview")
        self.assertEqual(payload["deployment.reference"], "abc123")
        self.assertEqual(payload["event.name"], "test.signal")
        self.assertEqual(payload["request.id"], "request_12345678")
        self.assertEqual(payload["trace_id"], context.trace_id)
        self.assertEqual(payload["span_id"], context.span_id)
        self.assertEqual(payload["outcome"], "success")
        self.assertEqual(payload["count"], 2)

    def test_mutation_classification_is_explicit(self) -> None:
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            self.assertTrue(is_mutation_method(method))
        for method in ("GET", "HEAD", "OPTIONS"):
            self.assertFalse(is_mutation_method(method))

    def test_slo_catalog_has_runbook_and_owner_for_every_alert(self) -> None:
        catalog = json.loads(SLO_PATH.read_text(encoding="utf-8"))
        runbook = RUNBOOK_PATH.read_text(encoding="utf-8")
        alert_ids = {alert["id"] for alert in catalog["alerts"]}
        required = {
            "PG-OBS-API-AVAILABILITY",
            "PG-OBS-API-LATENCY",
            "PG-OBS-MUTATION-ERROR-RATE",
            "PG-OBS-DATABASE-READINESS",
            "PG-OBS-PROVIDER-INGESTION",
            "PG-OBS-MEDIA-RECONCILIATION",
            "PG-OBS-BACKUP-PROTECTION",
        }

        self.assertEqual(alert_ids, required)
        for alert in catalog["alerts"]:
            self.assertEqual(alert["owner"], "PartGraph operator")
            self.assertTrue(alert["condition"])
            self.assertTrue(alert["runbook_anchor"])
            self.assertIn(f"### {alert['id']}", runbook)

        slo_alerts = {slo["alert"] for slo in catalog["slos"]}
        self.assertTrue(slo_alerts.issubset(alert_ids))

    def test_catalog_does_not_claim_unavailable_hobby_alert_delivery(self) -> None:
        catalog = json.loads(SLO_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            catalog["backend"]["custom_alert_delivery"],
            "blocked_on_current_vercel_plan",
        )
        self.assertEqual(
            catalog["backend"]["external_otlp_or_error_backend"],
            "not_configured",
        )
        for alert in catalog["alerts"]:
            if alert["id"] == "PG-OBS-BACKUP-PROTECTION":
                self.assertIn("manual_cutover_gate", alert["activation"])
            else:
                self.assertEqual(
                    alert["activation"],
                    "defined_not_active_on_current_hobby_plan",
                )

    def test_required_runtime_signals_are_wired(self) -> None:
        main_source = MAIN_PATH.read_text(encoding="utf-8")
        database_source = DATABASE_PATH.read_text(encoding="utf-8")
        nhtsa_source = NHTSA_PATH.read_text(encoding="utf-8")
        reference_parts_source = REFERENCE_PARTS_PATH.read_text(encoding="utf-8")
        photo_source = PHOTO_LIFECYCLE_PATH.read_text(encoding="utf-8")

        self.assertIn('"http.server.request"', main_source)
        self.assertIn('"error.unhandled"', main_source)
        self.assertIn('response.headers["traceparent"]', main_source)
        self.assertIn('"database.readiness"', database_source)
        self.assertIn('"provider.ingestion"', nhtsa_source)
        self.assertIn('"provider.name": "nhtsa"', nhtsa_source)
        self.assertIn('"provider.ingestion"', reference_parts_source)
        self.assertIn('"provider.name": "reference_parts"', reference_parts_source)
        self.assertIn('outcome="failure"', reference_parts_source)
        self.assertIn('outcome="success"', reference_parts_source)
        self.assertIn('"media.reconciliation.item"', photo_source)
        self.assertIn('"media.reconciliation.batch"', photo_source)


if __name__ == "__main__":
    unittest.main()
