from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "verify_hosted_nhtsa_ingestion.py"
SPEC = importlib.util.spec_from_file_location("hosted_nhtsa_proof", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load hosted NHTSA proof script")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class _FakeClient:
    def __init__(self, responses):
        self.responses = responses

    def _request(self, path):
        return 200, self.responses[path]


class HostedNhtsaProofContractTests(unittest.TestCase):
    def test_config_requires_same_host_for_access_url(self) -> None:
        values = {
            "PARTGRAPH_HOSTED_NHTSA_BASE_URL": "https://preview.example.test",
            "PARTGRAPH_HOSTED_NHTSA_ACCESS_URL": "https://other.example.test/?share=1",
            "PARTGRAPH_HOSTED_OPERATOR_IDENTIFIER": "operator@example.test",
            "PARTGRAPH_HOSTED_OPERATOR_PASSWORD": "not-a-real-secret",
        }
        with patch.dict(os.environ, values, clear=True):
            with self.assertRaises(MODULE.HostedProofError):
                MODULE._config()

    def test_config_requires_external_vehicle_query(self) -> None:
        values = {
            "PARTGRAPH_HOSTED_NHTSA_BASE_URL": "https://preview.example.test",
            "PARTGRAPH_HOSTED_OPERATOR_IDENTIFIER": "operator@example.test",
            "PARTGRAPH_HOSTED_OPERATOR_PASSWORD": "not-a-real-secret",
        }
        with patch.dict(os.environ, values, clear=True):
            with self.assertRaises(MODULE.HostedProofError):
                MODULE._config()

    def test_config_accepts_synthetic_vehicle_query(self) -> None:
        values = {
            "PARTGRAPH_HOSTED_NHTSA_BASE_URL": "https://preview.example.test",
            "PARTGRAPH_HOSTED_OPERATOR_IDENTIFIER": "operator@example.test",
            "PARTGRAPH_HOSTED_OPERATOR_PASSWORD": "not-a-real-secret",
            "PARTGRAPH_HOSTED_NHTSA_YEAR": "2099",
            "PARTGRAPH_HOSTED_NHTSA_MAKE": "Fixture Make",
            "PARTGRAPH_HOSTED_NHTSA_MODEL": "Fixture Model",
        }
        with patch.dict(os.environ, values, clear=True):
            config = MODULE._config()
        self.assertEqual(config.year, 2099)
        self.assertEqual(config.make, "Fixture Make")
        self.assertEqual(config.model, "Fixture Model")

    def test_binding_discovery_requires_ready_official_nhtsa_pair(self) -> None:
        client = _FakeClient(
            {
                "/api/v1/operator/access": {"role": "operator_admin"},
                "/api/v1/operator/providers": [
                    {
                        "id": "provider-disabled",
                        "provider_kind": "vehicle_data",
                        "enabled": False,
                        "base_url": "https://api.nhtsa.gov",
                    },
                    {
                        "id": "provider-live",
                        "provider_kind": "vehicle_data",
                        "enabled": True,
                        "base_url": "https://api.nhtsa.gov",
                    },
                    {
                        "id": "provider-other",
                        "provider_kind": "vehicle_data",
                        "enabled": True,
                        "base_url": "https://example.test",
                    },
                ],
                "/api/v1/operator/provider-source-bindings": [
                    {
                        "id": "binding-disabled",
                        "provider_connection_id": "provider-live",
                        "source_key": "nhtsa-recalls",
                        "ready_for_ingestion": False,
                    },
                    {
                        "id": "binding-live",
                        "provider_connection_id": "provider-live",
                        "source_key": "nhtsa-recalls",
                        "ready_for_ingestion": True,
                    },
                    {
                        "id": "binding-wrong-source",
                        "provider_connection_id": "provider-live",
                        "source_key": "other",
                        "ready_for_ingestion": True,
                    },
                ],
            }
        )
        binding = MODULE._find_nhtsa_binding(client)
        self.assertEqual(binding["id"], "binding-live")

    def test_audit_matching_requires_pending_candidate_publication_mode(self) -> None:
        config = MODULE.HostedProofConfig(
            base_url="https://preview.example.test",
            access_url=None,
            identifier="operator@example.test",
            password="not-a-real-secret",
            year=2099,
            make="Fixture Make",
            model="Fixture Model",
        )
        events = [
            {
                "id": "match",
                "action": "nhtsa_recall_query_staged",
                "target_id": "binding-live",
                "event_data": {
                    "year": 2099,
                    "make": "Fixture Make",
                    "model": "Fixture Model",
                    "publication_mode": "pending_candidates_only",
                },
            },
            {
                "id": "wrong-mode",
                "action": "nhtsa_recall_query_staged",
                "target_id": "binding-live",
                "event_data": {
                    "year": 2009,
                    "make": "Honda",
                    "model": "Civic",
                    "publication_mode": "canonical",
                },
            },
            {
                "id": "wrong-target",
                "action": "nhtsa_recall_query_staged",
                "target_id": "other-binding",
                "event_data": {
                    "year": 2009,
                    "make": "Honda",
                    "model": "Civic",
                    "publication_mode": "pending_candidates_only",
                },
            },
        ]
        self.assertEqual(
            MODULE._matching_audit_ids(events, binding_id="binding-live", config=config),
            {"match"},
        )


if __name__ == "__main__":
    unittest.main()
