from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REFERENCE_FLEET_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "reference_fleet" / "reference-fleet-v1.json"
)
EXPECTED_VEHICLE_COUNT = 5
EXPECTED_MVP_DOMAINS = {
    "routine_maintenance",
    "cooling",
    "brakes",
    "suspension_steering",
    "engine_peripheral",
    "lighting_body",
    "hvac_safe_mechanical",
    "sensor_simple_electrical",
    "fluids_and_bleeding",
    "post_replacement_dependency_boundary",
}


class ReferenceFleetIntegrityError(RuntimeError):
    pass


def load_reference_fleet(path: Path = REFERENCE_FLEET_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_reference_fleet(payload)
    return payload


def validate_reference_fleet(payload: dict[str, Any]) -> None:
    if payload.get("version") != 1:
        raise ReferenceFleetIntegrityError("Reference fleet version must be 1.")
    if payload.get("market") != "US":
        raise ReferenceFleetIntegrityError("Reference fleet is currently US-only.")

    rules = payload.get("product_rules")
    if not isinstance(rules, dict):
        raise ReferenceFleetIntegrityError("Reference fleet product rules are missing.")
    if rules.get("computer_service") != "unsupported_indefinitely":
        raise ReferenceFleetIntegrityError(
            "Computer-dependent service must remain unsupported for the MVP."
        )
    if rules.get("guided_physical_bleeding") is not True:
        raise ReferenceFleetIntegrityError(
            "Physical fluid/air bleeding must remain an allowed guided domain."
        )

    declared_domains = payload.get("required_mvp_domains")
    if set(declared_domains or []) != EXPECTED_MVP_DOMAINS:
        raise ReferenceFleetIntegrityError("Reference fleet MVP domains changed unexpectedly.")

    vehicles = payload.get("vehicles")
    if not isinstance(vehicles, list) or len(vehicles) != EXPECTED_VEHICLE_COUNT:
        raise ReferenceFleetIntegrityError(
            f"Reference fleet must contain exactly {EXPECTED_VEHICLE_COUNT} vehicles."
        )

    keys: set[str] = set()
    covered_domains: set[str] = set()
    for vehicle in vehicles:
        if not isinstance(vehicle, dict):
            raise ReferenceFleetIntegrityError("Reference fleet vehicle entry is malformed.")
        key = vehicle.get("key")
        if not isinstance(key, str) or not key:
            raise ReferenceFleetIntegrityError("Every reference vehicle requires a stable key.")
        if key in keys:
            raise ReferenceFleetIntegrityError(f"Duplicate reference vehicle key: {key}")
        keys.add(key)

        required_identity = (
            "year",
            "make",
            "model",
            "trim",
            "body_style",
            "engine",
            "transmission",
            "drivetrain",
        )
        missing = [field for field in required_identity if not vehicle.get(field)]
        if missing:
            raise ReferenceFleetIntegrityError(
                f"Reference vehicle {key} is missing: {', '.join(missing)}"
            )
        if vehicle.get("configuration_status") != "verified_reference":
            raise ReferenceFleetIntegrityError(
                f"Reference vehicle {key} is not marked verified_reference."
            )

        evidence = vehicle.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ReferenceFleetIntegrityError(
                f"Reference vehicle {key} has no source provenance."
            )
        for source in evidence:
            if not isinstance(source, dict) or not source.get("url") or not source.get("source"):
                raise ReferenceFleetIntegrityError(
                    f"Reference vehicle {key} contains incomplete evidence metadata."
                )

        domains = vehicle.get("mvp_domains")
        if not isinstance(domains, list):
            raise ReferenceFleetIntegrityError(
                f"Reference vehicle {key} has no MVP-domain allocation."
            )
        covered_domains.update(str(domain) for domain in domains)

    missing_domains = EXPECTED_MVP_DOMAINS - covered_domains
    if missing_domains:
        raise ReferenceFleetIntegrityError(
            "Reference fleet does not cover required MVP domains: "
            + ", ".join(sorted(missing_domains))
        )
