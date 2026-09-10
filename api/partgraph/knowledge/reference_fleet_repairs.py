from __future__ import annotations

import json
from pathlib import Path

from .reference_fleet import load_reference_fleet
from .support_boundaries import COMPUTER_SERVICE_BOUNDARY_ACTION_KEY

CORPUS_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "reference_fleet"
    / "repair-corpus-v1.json"
)

DEFERRED_GUIDED_OPERATIONS = {
    "calibration",
    "initialization",
    "aiming",
    "adjustment",
    "priming",
    "torque_sequence",
}
COMPUTER_DEPENDENT_TERMS = {
    "scan tool",
    "service tool",
    "diagnostic computer",
    "programming",
    "coding",
    "relearn",
    "calibration",
    "initialization",
}
ALLOWED_STATUSES = {"verified", "candidate"}


def _normalized_text(value: object) -> str:
    return " ".join(str(value).casefold().replace("-", " ").replace("_", " ").split())


def _validate_requirement(repair: dict[str, object], requirement: dict[str, object]) -> None:
    if not requirement.get("key") or not requirement.get("category") or not requirement.get("name"):
        raise ValueError(f"{repair['repair_key']} contains an incomplete requirement")
    if requirement.get("quantity") is None and repair.get("verification_status") == "verified":
        raise ValueError(
            f"verified repair {repair['repair_key']} cannot publish an unknown requirement quantity"
        )


def _validate_action(repair: dict[str, object], action: dict[str, object]) -> None:
    action_key = str(action.get("key", ""))
    if not action_key or not action.get("title") or not action.get("instruction"):
        raise ValueError(f"{repair['repair_key']} contains an incomplete action")

    text = _normalized_text(
        f"{action_key} {action.get('title', '')} {action.get('instruction', '')}"
    )
    deferred = {operation for operation in DEFERRED_GUIDED_OPERATIONS if operation in text}
    if deferred:
        raise ValueError(
            f"{repair['repair_key']} attempts to guide deferred operation(s): {sorted(deferred)}"
        )

    if action_key != COMPUTER_SERVICE_BOUNDARY_ACTION_KEY:
        computer_terms = {term for term in COMPUTER_DEPENDENT_TERMS if term in text}
        if computer_terms:
            raise ValueError(
                f"{repair['repair_key']} attempts computer-dependent guidance: "
                f"{sorted(computer_terms)}"
            )


def load_reference_fleet_repair_corpus() -> dict[str, object]:
    payload = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("reference fleet repair corpus schema_version must be 1")

    policy = payload.get("verification_policy")
    if not isinstance(policy, dict):
        raise ValueError("reference fleet repair corpus is missing verification_policy")
    if policy.get("collector_rules_inherited") is not False:
        raise ValueError("reference fleet repair corpus must not inherit collector admission rules")
    if policy.get("computer_service") != "unsupported_indefinitely":
        raise ValueError("computer-dependent vehicle service must remain unsupported indefinitely")
    if policy.get("physical_bleeding_supported") is not True:
        raise ValueError("physical fluid/air bleeding must remain an allowed MVP operation")
    if set(policy.get("deferred_guided_operations", [])) != DEFERRED_GUIDED_OPERATIONS:
        raise ValueError("deferred guided-operation boundary changed unexpectedly")

    fleet = load_reference_fleet()
    vehicle_keys = {str(vehicle["vehicle_key"]) for vehicle in fleet["vehicles"]}
    repairs = payload.get("repairs")
    if not isinstance(repairs, list) or not repairs:
        raise ValueError("reference fleet repair corpus must contain repairs")

    seen: set[tuple[str, str]] = set()
    for raw_repair in repairs:
        if not isinstance(raw_repair, dict):
            raise ValueError("repair entries must be objects")
        repair = raw_repair
        vehicle_key = str(repair.get("vehicle_key", ""))
        repair_key = str(repair.get("repair_key", ""))
        if vehicle_key not in vehicle_keys:
            raise ValueError(f"repair references unknown reference vehicle: {vehicle_key}")
        if not repair_key:
            raise ValueError("repair_key is required")
        identity = (vehicle_key, repair_key)
        if identity in seen:
            raise ValueError(f"duplicate reference repair: {identity}")
        seen.add(identity)

        status = repair.get("verification_status")
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"unsupported reference repair verification status: {status}")

        evidence = repair.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"{repair_key} has no source evidence")
        for source in evidence:
            if not isinstance(source, dict) or not source.get("url") or not source.get("supports"):
                raise ValueError(f"{repair_key} contains incomplete source provenance")

        requirements = repair.get("requirements")
        actions = repair.get("actions")
        if not isinstance(requirements, list) or not isinstance(actions, list):
            raise ValueError(f"{repair_key} requirements/actions must be lists")
        for requirement in requirements:
            if not isinstance(requirement, dict):
                raise ValueError(f"{repair_key} contains a non-object requirement")
            _validate_requirement(repair, requirement)
        for action in actions:
            if not isinstance(action, dict):
                raise ValueError(f"{repair_key} contains a non-object action")
            _validate_action(repair, action)

        if status == "verified" and not actions:
            raise ValueError(f"verified repair {repair_key} must contain guided actions")
        if status == "candidate" and actions:
            raise ValueError(
                f"candidate repair {repair_key} cannot expose guided actions before verification"
            )

    return payload


def verified_reference_repairs() -> list[dict[str, object]]:
    payload = load_reference_fleet_repair_corpus()
    return [
        repair
        for repair in payload["repairs"]
        if isinstance(repair, dict) and repair.get("verification_status") == "verified"
    ]


__all__ = [
    "CORPUS_PATH",
    "DEFERRED_GUIDED_OPERATIONS",
    "load_reference_fleet_repair_corpus",
    "verified_reference_repairs",
]
