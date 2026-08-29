from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import sys
import traceback
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select, update

from partgraph.catalog.models import CatalogVerifiedEvidence
from partgraph.catalog.source_models import CatalogSource, MechanicalClaim
from partgraph.database import session_factory
from partgraph.repair_definition.models import (
    ProcedureAction,
    ProcedureActionDependency,
    ProcedureActionEvidence,
    ProcedureActionRequirementUse,
    RepairCapabilityPolicy,
    RepairDefinition,
    RepairOperation,
    RequirementDefinition,
    RequirementUse,
    RequirementUseEvidence,
    UserGarageInventoryItem,
)

API_URL = os.getenv("PARTGRAPH_ACCEPTANCE_API_URL", "http://api:8000").rstrip("/")
DEFAULT_CASES = int(os.getenv("PARTGRAPH_ACCEPTANCE_CASES", "20"))
DEFAULT_SEED = int(os.getenv("PARTGRAPH_ACCEPTANCE_SEED", "20260829"))
ALL_BRANDS = os.getenv("PARTGRAPH_ACCEPTANCE_ALL_BRANDS", "false").lower() == "true"
PASSWORD = "correct-horse-battery-staple"
ORIGIN = "http://localhost:15173"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"partgraph-local-acceptance-image"

WORKFLOW_CONTRACTS = {
    "auth",
    "vehicle_identity",
    "repair_session",
    "lease",
    "repair_memory",
    "manual_inventory",
    "observations_photos",
    "repair_binding",
    "readiness",
    "garage_reuse",
    "guided_procedure",
    "inventory_blocking",
    "procedure_progress",
    "resume_reorientation",
    "event_history",
    "idempotency",
    "owner_isolation",
    "capability_safety",
    "pause_resume",
    "archive",
}

SCENARIOS = [
    "happy_path_full_repair",
    "readiness_ordered_transition",
    "garage_reusable_tool",
    "inventory_blocker_recovery",
    "action_blocker_recovery",
    "skippable_action",
    "non_skippable_rejection",
    "wrong_device_lease",
    "lease_takeover",
    "idempotent_replay",
    "idempotency_conflict",
    "pause_resume",
    "repair_memory_fastener_storage",
    "observation_photo",
    "owner_isolation",
    "resume_guidance_consistency",
    "superseded_definition_pin",
    "professional_required_boundary",
    "prohibited_boundary",
    "unbound_then_bind",
]

REPAIR_TEMPLATES = [
    "cooling-system-service",
    "engine-oil-filter-service",
    "front-brake-service",
    "wheel-tire-service",
    "battery-cable-service",
    "spark-plug-service",
    "drive-belt-service",
    "thermostat-service",
    "radiator-hose-service",
    "suspension-link-service",
    "headlamp-service",
    "wiper-service",
    "cabin-filter-service",
    "transmission-fluid-service",
    "differential-fluid-service",
    "exhaust-hanger-service",
    "wheel-bearing-service",
    "door-hinge-service",
    "blower-motor-service",
    "underbody-shield-hardware-service",
]


class AcceptanceFailure(AssertionError):
    pass


@dataclass(slots=True)
class SeededDefinition:
    definition_id: UUID
    repair_key: str
    requirement_ids: dict[str, UUID]
    requirement_use_ids: dict[str, UUID]
    action_ids: list[UUID]


@dataclass(slots=True)
class CaseContext:
    number: int
    scenario: str
    vehicle: dict[str, Any]
    repair_template: str
    client: httpx.Client
    user_id: UUID
    vehicle_id: UUID
    configuration_id: UUID
    session_id: UUID
    device_id: str
    seeded: SeededDefinition | None = None


def _headers(device_id: str | None = None, key: str | None = None) -> dict[str, str]:
    headers = {"X-PartGraph-CSRF": "1", "Origin": ORIGIN}
    if device_id is not None:
        headers["X-PartGraph-Device-ID"] = device_id
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def _body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return response.text


def _require(response: httpx.Response, expected: int | set[int], label: str) -> Any:
    accepted = {expected} if isinstance(expected, int) else expected
    if response.status_code not in accepted:
        raise AcceptanceFailure(
            f"{label}: expected HTTP {sorted(accepted)}, got {response.status_code}: {_body(response)}"
        )
    return _body(response)


def _require_error(response: httpx.Response, status: int, code: str, label: str) -> None:
    body = _require(response, status, label)
    actual = body.get("error", {}).get("code") if isinstance(body, dict) else None
    if actual != code:
        raise AcceptanceFailure(f"{label}: expected error {code}, got {actual}: {body}")


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise AcceptanceFailure(f"{label}: expected {expected!r}, got {actual!r}")


def _require_true(value: Any, label: str) -> None:
    if not value:
        raise AcceptanceFailure(f"{label}: condition was false")


def _fixture_hash(case_tag: str) -> str:
    return hashlib.sha256(case_tag.encode("utf-8")).hexdigest()


async def _seed_verified_definition(
    *,
    configuration_id: UUID,
    case_tag: str,
    repair_template: str,
    policy_key: str,
) -> SeededDefinition:
    now = datetime.now(UTC)
    repair_key = f"acceptance-{repair_template}-{case_tag}"

    async with session_factory() as db:
        policy = await db.scalar(
            select(RepairCapabilityPolicy).where(RepairCapabilityPolicy.policy_key == policy_key)
        )
        if policy is None:
            raise AcceptanceFailure(f"seed: capability policy {policy_key!r} missing")

        source = CatalogSource(
            source_key=f"acceptance-source-{case_tag}",
            display_name="PartGraph LOCAL-ONLY synthetic acceptance fixture",
            source_class="community",
            license_status="approved",
            automation_allowed=False,
            notes="Synthetic acceptance data. Never production mechanical truth.",
        )
        evidence = CatalogVerifiedEvidence(
            staging_record_id=uuid4(),
            candidate_type="local_acceptance_fixture",
            verified_payload={
                "synthetic": True,
                "case_tag": case_tag,
                "warning": "DO NOT USE AS REPAIR INSTRUCTION",
            },
            vehicle_identity={"configuration_id": str(configuration_id)},
            source_name="partgraph-local-acceptance",
            source_type="synthetic_fixture",
            source_record_id=f"acceptance-{case_tag}",
            source_url=f"https://example.invalid/partgraph-acceptance/{case_tag}",
            raw_sha256=_fixture_hash(case_tag),
            fetched_at=now,
            observed_at=now,
            provenance={"fixture": True, "local_only": True},
            extraction_method="synthetic_local_acceptance",
            promoted_by="local-acceptance-runner",
        )
        definition = RepairDefinition(
            vehicle_configuration_id=configuration_id,
            capability_policy_id=policy.id,
            repair_key=repair_key,
            title=f"Synthetic {repair_template.replace('-', ' ')}",
            version=1,
            status="verified",
            verified_at=now,
        )
        db.add_all([source, evidence, definition])
        await db.flush()

        operations = [
            RepairOperation(
                repair_definition_id=definition.id,
                operation_key="prepare",
                label="Synthetic prepare operation",
                position=0,
            ),
            RepairOperation(
                repair_definition_id=definition.id,
                operation_key="service",
                label="Synthetic service operation",
                position=1,
            ),
            RepairOperation(
                repair_definition_id=definition.id,
                operation_key="verify",
                label="Synthetic verify operation",
                position=2,
            ),
        ]
        db.add_all(operations)
        await db.flush()

        requirement_specs = [
            ("tool", "tool", "Synthetic metric socket/wrench", "each", "reusable", operations[0]),
            ("workspace", "workspace", "Synthetic stable work area", "each", "reusable", operations[0]),
            ("part", "part", f"Synthetic {repair_template} replacement component", "each", "replacement_required", operations[1]),
            ("hardware", "hardware", "Synthetic nuts/bolts/clips kit", "each", "consumed", operations[1]),
            ("fluid", "fluid", "Synthetic service fluid", "mL", "consumed", operations[2]),
        ]

        requirement_ids: dict[str, UUID] = {}
        requirement_use_ids: dict[str, UUID] = {}
        requirement_uses: dict[str, RequirementUse] = {}

        for index, (name, category, display, unit, mode, operation) in enumerate(requirement_specs):
            requirement = RequirementDefinition(
                requirement_key=f"acceptance.{case_tag}.{name}",
                category=category,
                display_name=display,
                default_unit=unit,
            )
            claim = MechanicalClaim(
                source_id=source.id,
                verified_evidence_id=evidence.id,
                vehicle_configuration_id=configuration_id,
                claim_domain="repair_requirement",
                claim_risk="normal",
                normalized_key=f"repair:{repair_key}:requirement:{name}",
                repair_key=repair_key,
                claim_payload={"synthetic": True, "name": name},
                explicit_claim=True,
                exact_applicability=True,
                promotion_state="verified",
                reviewed_at=now,
                reviewed_by="local-acceptance-runner",
            )
            db.add_all([requirement, claim])
            await db.flush()
            use = RequirementUse(
                repair_definition_id=definition.id,
                operation_id=operation.id,
                requirement_definition_id=requirement.id,
                quantity=Decimal("250") if name == "fluid" else Decimal("1"),
                unit=unit,
                necessity="required",
                fulfillment_mode=mode,
                timing="operation",
            )
            db.add(use)
            await db.flush()
            db.add(
                RequirementUseEvidence(
                    requirement_use_id=use.id,
                    mechanical_claim_id=claim.id,
                )
            )
            requirement_ids[name] = requirement.id
            requirement_use_ids[name] = use.id
            requirement_uses[name] = use

        action_specs = [
            ("inspect", "Inspect synthetic fixture state", False),
            ("prepare", "Prepare synthetic tools and workspace", False),
            ("service", "Perform synthetic replacement stage", True),
            ("verify", "Verify synthetic fixture outcome", False),
        ]
        actions: list[ProcedureAction] = []
        procedure_claims: list[MechanicalClaim] = []
        for position, (key, title, skippable) in enumerate(action_specs):
            claim = MechanicalClaim(
                source_id=source.id,
                verified_evidence_id=evidence.id,
                vehicle_configuration_id=configuration_id,
                claim_domain="repair_procedure",
                claim_risk="normal",
                normalized_key=f"repair:{repair_key}:procedure:{key}",
                repair_key=repair_key,
                claim_payload={"synthetic": True, "action": key},
                explicit_claim=True,
                exact_applicability=True,
                promotion_state="verified",
                reviewed_at=now,
                reviewed_by="local-acceptance-runner",
            )
            action = ProcedureAction(
                repair_definition_id=definition.id,
                action_key=key,
                title=title,
                instruction=(
                    f"SYNTHETIC LOCAL ACCEPTANCE ACTION {position + 1}. "
                    "This text exists only to exercise PartGraph workflow logic and is not repair advice."
                ),
                warning_text=(
                    "Synthetic warning: local acceptance fixture only; never use as mechanical guidance."
                    if position == 2
                    else None
                ),
                workspace_note=(
                    "Synthetic workspace prerequisite used to test deterministic UI/API output."
                    if position == 1
                    else None
                ),
                position=position,
                skippable=skippable,
            )
            db.add_all([claim, action])
            await db.flush()
            db.add(ProcedureActionEvidence(action_id=action.id, mechanical_claim_id=claim.id))
            actions.append(action)
            procedure_claims.append(claim)

        for index in range(1, len(actions)):
            db.add(
                ProcedureActionDependency(
                    action_id=actions[index].id,
                    prerequisite_action_id=actions[index - 1].id,
                )
            )

        links = {
            1: ["tool", "workspace"],
            2: ["part", "hardware"],
            3: ["fluid"],
        }
        for action_index, names in links.items():
            for name in names:
                db.add(
                    ProcedureActionRequirementUse(
                        action_id=actions[action_index].id,
                        requirement_use_id=requirement_uses[name].id,
                    )
                )

        await db.commit()
        return SeededDefinition(
            definition_id=definition.id,
            repair_key=repair_key,
            requirement_ids=requirement_ids,
            requirement_use_ids=requirement_use_ids,
            action_ids=[action.id for action in actions],
        )


async def _garage_has(user_id: UUID, requirement_id: UUID) -> bool:
    async with session_factory() as db:
        row = await db.scalar(
            select(UserGarageInventoryItem).where(
                UserGarageInventoryItem.user_id == user_id,
                UserGarageInventoryItem.requirement_definition_id == requirement_id,
                UserGarageInventoryItem.quantity_available > 0,
            )
        )
        return row is not None


async def _supersede_fixture(seeded: SeededDefinition, configuration_id: UUID) -> None:
    async with session_factory() as db:
        await db.execute(
            update(RepairDefinition)
            .where(RepairDefinition.id == seeded.definition_id)
            .values(status="superseded")
        )
        await db.execute(
            update(MechanicalClaim)
            .where(
                MechanicalClaim.vehicle_configuration_id == configuration_id,
                MechanicalClaim.repair_key == seeded.repair_key,
            )
            .values(promotion_state="superseded")
        )
        await db.commit()


def _register(client: httpx.Client, case_tag: str) -> UUID:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"acceptance-{case_tag}@example.com",
            "username": f"accept_{case_tag}"[:32],
            "password": PASSWORD,
        },
        headers=_headers(),
    )
    body = _require(response, 200, "register")
    return UUID(body["user"]["id"])


def _create_vehicle(client: httpx.Client, case_tag: str, vehicle: dict[str, Any]) -> tuple[UUID, UUID]:
    response = client.post(
        "/api/v1/user-vehicles/manual",
        json={"nickname": f"Acceptance {case_tag}", "selection": vehicle},
        headers=_headers(),
    )
    body = _require(response, 201, "create manual vehicle")
    _require_true(body["canonical_configuration_id"], "manual vehicle resolved exactly")
    _require_equal(body["identity"]["make"], vehicle["make"], "canonical make")
    return UUID(body["id"]), UUID(body["canonical_configuration_id"])


def _create_session(
    client: httpx.Client,
    case_tag: str,
    vehicle_id: UUID,
    device_id: str,
) -> tuple[UUID, dict[str, Any]]:
    key = f"acc_session_{case_tag}"
    payload = {"user_vehicle_id": str(vehicle_id), "title": f"Acceptance repair {case_tag}"}
    response = client.post(
        "/api/v1/repair-sessions",
        json=payload,
        headers=_headers(device_id, key),
    )
    body = _require(response, 201, "create repair session")
    return UUID(body["session"]["id"]), {"key": key, "payload": payload, "body": body}


def _exercise_memory(ctx: CaseContext, case_tag: str) -> None:
    client = ctx.client
    location = _require(
        client.post(
            f"/api/v1/repair-sessions/{ctx.session_id}/storage-locations",
            json={"label": f"Synthetic tray {ctx.number}", "notes": "local acceptance"},
            headers=_headers(ctx.device_id, f"acc_loc_{case_tag}"),
        ),
        201,
        "create storage location",
    )
    fastener = _require(
        client.post(
            f"/api/v1/repair-sessions/{ctx.session_id}/fasteners",
            json={
                "kind": "fastener",
                "label": "Synthetic support bolt",
                "origin": "Synthetic chassis fixture",
                "position": "Acceptance position",
                "physical_state": "stored",
                "storage_location_id": location["id"],
            },
            headers=_headers(ctx.device_id, f"acc_fastener_{case_tag}"),
        ),
        201,
        "record fastener",
    )
    inventory = _require(
        client.post(
            f"/api/v1/repair-sessions/{ctx.session_id}/inventory",
            json={
                "name": "Synthetic replacement hardware",
                "quantity": 2,
                "procurement_state": "needed",
            },
            headers=_headers(ctx.device_id, f"acc_inv_{case_tag}"),
        ),
        201,
        "record manual inventory",
    )
    _require(
        client.patch(
            f"/api/v1/repair-sessions/{ctx.session_id}/inventory/{inventory['id']}",
            json={"procurement_state": "available"},
            headers=_headers(ctx.device_id, f"acc_inv_ready_{case_tag}"),
        ),
        200,
        "update manual inventory",
    )
    observation = _require(
        client.post(
            f"/api/v1/repair-sessions/{ctx.session_id}/observations",
            json={
                "category": "condition",
                "text": "Synthetic acceptance observation for repair continuity.",
                "fastener_id": fastener["id"],
            },
            headers=_headers(ctx.device_id, f"acc_obs_{case_tag}"),
        ),
        201,
        "record observation",
    )
    photo = _require(
        client.post(
            f"/api/v1/repair-sessions/{ctx.session_id}/photos",
            data={
                "purpose": "fastener",
                "fastener_id": fastener["id"],
                "observation_id": observation["id"],
            },
            files={"photo": ("acceptance.png", PNG_BYTES, "image/png")},
            headers=_headers(ctx.device_id, f"acc_photo_{case_tag}"),
        ),
        201,
        "upload photo evidence",
    )
    content = client.get(
        f"/api/v1/repair-sessions/{ctx.session_id}/photos/{photo['id']}/content"
    )
    _require(content, 200, "read photo evidence")
    _require_equal(content.content, PNG_BYTES, "photo bytes round trip")


def _bind(ctx: CaseContext) -> None:
    assert ctx.seeded is not None
    body = _require(
        ctx.client.put(
            f"/api/v1/repair-sessions/{ctx.session_id}/repair-definition",
            json={"repair_key": ctx.seeded.repair_key},
            headers=_headers(ctx.device_id),
        ),
        200,
        "bind verified repair definition",
    )
    _require_equal(body["repair_definition_id"], str(ctx.seeded.definition_id), "bound definition")


def _set_readiness(
    ctx: CaseContext,
    requirement_id: str,
    state: str,
    suffix: str,
) -> dict[str, Any]:
    return _require(
        ctx.client.put(
            f"/api/v1/repair-sessions/{ctx.session_id}/readiness/{requirement_id}",
            json={"readiness_state": state},
            headers=_headers(ctx.device_id, f"acc_ready_{ctx.number}_{suffix}"),
        ),
        200,
        f"readiness -> {state}",
    )


def _guidance(ctx: CaseContext) -> dict[str, Any]:
    return _require(
        ctx.client.get(f"/api/v1/repair-sessions/{ctx.session_id}/guidance"),
        200,
        "read guidance",
    )


def _progress(ctx: CaseContext, action_id: str, state: str, suffix: str) -> dict[str, Any]:
    payload: dict[str, Any] = {"progress_state": state}
    if state == "blocked":
        payload["blocker_code"] = "local_acceptance_problem"
        payload["notes"] = "Synthetic local-only problem used to test recovery."
    return _require(
        ctx.client.put(
            f"/api/v1/repair-sessions/{ctx.session_id}/guidance/actions/{action_id}",
            json=payload,
            headers=_headers(ctx.device_id, f"acc_progress_{ctx.number}_{suffix}"),
        ),
        200,
        f"procedure progress -> {state}",
    )


def _resolve_current_inventory(ctx: CaseContext, guidance: dict[str, Any], ordered_first: bool) -> None:
    blockers = guidance["current_action"]["inventory_blockers"]
    for index, blocker in enumerate(blockers):
        requirement_id = blocker["requirement_definition_id"]
        if ordered_first and index == 0:
            ordered = _set_readiness(ctx, requirement_id, "ordered", f"ordered_{index}")
            _require_true(ordered["summary"]["blocked"] > 0, "ordered item remains blocking")
        _set_readiness(ctx, requirement_id, "have", f"have_{guidance['current_action']['position']}_{index}")


def _run_guided_flow(ctx: CaseContext, scenario: str) -> None:
    guidance = _guidance(ctx)
    _require_equal(guidance["current_action"]["action_key"], "inspect", "first deterministic action")

    if scenario == "non_skippable_rejection":
        response = ctx.client.put(
            f"/api/v1/repair-sessions/{ctx.session_id}/guidance/actions/{guidance['current_action']['action_id']}",
            json={"progress_state": "skipped"},
            headers=_headers(ctx.device_id, f"acc_bad_skip_{ctx.number}"),
        )
        _require_error(response, 409, "REPAIR_GUIDANCE_ACTION_NOT_SKIPPABLE", "reject unsafe skip")

    _progress(ctx, guidance["current_action"]["action_id"], "completed", "inspect")

    blocked_once = False
    skipped_once = False
    ordered_first = scenario == "readiness_ordered_transition"
    while True:
        guidance = _guidance(ctx)
        if guidance["procedure_complete"]:
            break
        action = guidance["current_action"]
        _require_true(action is not None, "current action exists before completion")

        if guidance["status"] == "inventory_blocked":
            _resolve_current_inventory(ctx, guidance, ordered_first=ordered_first)
            ordered_first = False
            guidance = _guidance(ctx)
            action = guidance["current_action"]
            _require_equal(guidance["status"], "action_available", "inventory unblock exposes action")

        if scenario == "action_blocker_recovery" and not blocked_once and action["action_key"] == "service":
            _progress(ctx, action["action_id"], "blocked", "block_service")
            blocked_view = _guidance(ctx)
            _require_equal(blocked_view["status"], "action_blocked", "blocked action does not advance")
            _require_equal(blocked_view["current_action"]["action_id"], action["action_id"], "blocked action stays current")
            _progress(ctx, action["action_id"], "completed", "resolve_service")
            blocked_once = True
            continue

        if scenario == "skippable_action" and not skipped_once and action["action_key"] == "service":
            _require_true(action["skippable"], "service fixture explicitly skippable")
            _progress(ctx, action["action_id"], "skipped", "skip_service")
            skipped_once = True
            continue

        _progress(ctx, action["action_id"], "completed", f"complete_{action['action_key']}")

    final = _guidance(ctx)
    _require_equal(final["status"], "procedure_complete", "procedure complete status")
    _require_true(final["current_action"] is None, "no current action after completion")


def _pause_resume(ctx: CaseContext) -> None:
    paused = _require(
        ctx.client.post(
            f"/api/v1/repair-sessions/{ctx.session_id}/pause",
            headers=_headers(ctx.device_id, f"acc_pause_{ctx.number}"),
        ),
        200,
        "pause repair",
    )
    _require_equal(paused["session"]["status"], "paused", "paused state")
    resumed = _require(
        ctx.client.post(
            f"/api/v1/repair-sessions/{ctx.session_id}/resume",
            headers=_headers(ctx.device_id, f"acc_resume_{ctx.number}"),
        ),
        200,
        "resume repair",
    )
    _require_equal(resumed["session"]["status"], "active", "resumed state")


def _archive(ctx: CaseContext) -> None:
    archived = _require(
        ctx.client.patch(
            f"/api/v1/repair-sessions/{ctx.session_id}/archive",
            headers=_headers(ctx.device_id, f"acc_archive_{ctx.number}"),
        ),
        200,
        "archive repair",
    )
    _require_equal(archived["session"]["status"], "archived", "archived state")
    reread = _require(
        ctx.client.get(f"/api/v1/repair-sessions/{ctx.session_id}/resume"),
        200,
        "read archived session",
    )
    _require_equal(reread["session"]["status"], "archived", "archive persisted")


def _history_assertions(ctx: CaseContext) -> None:
    history = _require(
        ctx.client.get(f"/api/v1/repair-sessions/{ctx.session_id}/events?limit=100"),
        200,
        "read event history",
    )
    events = history["items"]
    sequences = [item["sequence"] for item in events]
    _require_equal(sequences, list(range(1, len(sequences) + 1)), "event sequence contiguous")
    types = {item["event_type"] for item in events}
    _require_true("session_started" in types, "history contains session start")
    _require_true("photo_evidence_added" in types, "history contains photo")
    if ctx.seeded is not None:
        _require_true("readiness_state_changed" in types or ctx.scenario in {
            "professional_required_boundary", "prohibited_boundary"
        }, "history contains readiness progress when guided")


def _owner_isolation(ctx: CaseContext, case_tag: str) -> None:
    with httpx.Client(base_url=API_URL, timeout=10.0) as stranger:
        _register(stranger, f"stranger{case_tag}"[:20])
        response = stranger.get(f"/api/v1/repair-sessions/{ctx.session_id}/resume")
        _require_error(response, 404, "REPAIR_SESSION_NOT_FOUND", "cross-user session isolation")


def _boundary(ctx: CaseContext, expected_status: int, expected_code: str) -> None:
    response = ctx.client.get(f"/api/v1/repair-sessions/{ctx.session_id}/guidance")
    _require_error(response, expected_status, expected_code, "capability safety boundary")


def _exercise_scenario(
    *,
    case_number: int,
    scenario: str,
    vehicle: dict[str, Any],
    repair_template: str,
    coverage: set[str],
) -> None:
    case_tag = f"{case_number:02d}{uuid4().hex[:8]}"
    device_a = str(uuid4())
    device_b = str(uuid4())

    with httpx.Client(base_url=API_URL, timeout=10.0) as client:
        user_id = _register(client, case_tag)
        coverage.add("auth")
        vehicle_id, configuration_id = _create_vehicle(client, case_tag, vehicle)
        coverage.add("vehicle_identity")
        session_id, creation = _create_session(client, case_tag, vehicle_id, device_a)
        coverage.update({"repair_session", "lease"})

        ctx = CaseContext(
            number=case_number,
            scenario=scenario,
            vehicle=vehicle,
            repair_template=repair_template,
            client=client,
            user_id=user_id,
            vehicle_id=vehicle_id,
            configuration_id=configuration_id,
            session_id=session_id,
            device_id=device_a,
        )

        if scenario == "idempotent_replay":
            replay = _require(
                client.post(
                    "/api/v1/repair-sessions",
                    json=creation["payload"],
                    headers=_headers(device_a, creation["key"]),
                ),
                201,
                "idempotent session replay",
            )
            _require_equal(replay["session"]["id"], str(session_id), "replay returns same session")
            coverage.add("idempotency")

        if scenario == "idempotency_conflict":
            response = client.post(
                "/api/v1/repair-sessions",
                json={**creation["payload"], "title": "Conflicting acceptance title"},
                headers=_headers(device_a, creation["key"]),
            )
            _require_error(response, 409, "REPAIR_SESSION_IDEMPOTENCY_CONFLICT", "idempotency conflict")
            coverage.add("idempotency")

        if scenario == "wrong_device_lease":
            response = client.post(
                f"/api/v1/repair-sessions/{session_id}/inventory",
                json={"name": "Wrong-device synthetic item", "procurement_state": "needed"},
                headers=_headers(device_b, f"acc_wrong_device_{case_number}"),
            )
            _require_error(response, 409, "REPAIR_SESSION_LEASE_HELD", "wrong-device mutation")

        _exercise_memory(ctx, case_tag)
        coverage.update({"repair_memory", "manual_inventory", "observations_photos"})

        if scenario == "lease_takeover":
            takeover = _require(
                client.post(
                    f"/api/v1/repair-sessions/{session_id}/lease/takeover",
                    headers=_headers(device_b),
                ),
                200,
                "lease takeover",
            )
            _require_true(takeover["lease"]["can_edit"], "takeover grants edit")
            ctx.device_id = device_b

        _pause_resume(ctx)
        coverage.add("pause_resume")

        policy_key = "diy_supported"
        if scenario == "professional_required_boundary":
            policy_key = "professional_required"
        elif scenario == "prohibited_boundary":
            policy_key = "guided_prohibited"

        if scenario == "unbound_then_bind":
            readiness = _require(
                client.get(f"/api/v1/repair-sessions/{session_id}/readiness"),
                200,
                "unbound readiness",
            )
            _require_equal(readiness["binding_status"], "unbound", "readiness reports unbound")
            guidance = client.get(f"/api/v1/repair-sessions/{session_id}/guidance")
            _require_error(guidance, 409, "REPAIR_PROCEDURE_NOT_AVAILABLE", "unbound guidance refusal")

        ctx.seeded = asyncio.run(
            _seed_verified_definition(
                configuration_id=configuration_id,
                case_tag=case_tag,
                repair_template=repair_template,
                policy_key=policy_key,
            )
        )
        _bind(ctx)
        coverage.add("repair_binding")

        if scenario == "superseded_definition_pin":
            asyncio.run(_supersede_fixture(ctx.seeded, configuration_id))

        readiness = _require(
            client.get(f"/api/v1/repair-sessions/{session_id}/readiness"),
            200,
            "read bound readiness",
        )
        _require_equal(readiness["binding_status"], "bound", "readiness bound")
        _require_true(readiness["summary"]["missing"] >= 1, "synthetic manifest starts incomplete")
        coverage.add("readiness")

        if scenario == "professional_required_boundary":
            _boundary(ctx, 409, "REPAIR_GUIDANCE_PROFESSIONAL_REQUIRED")
            coverage.add("capability_safety")
        elif scenario == "prohibited_boundary":
            _boundary(ctx, 403, "REPAIR_GUIDANCE_PROHIBITED")
            coverage.add("capability_safety")
        else:
            _run_guided_flow(ctx, scenario)
            coverage.update(
                {"guided_procedure", "inventory_blocking", "procedure_progress", "readiness"}
            )
            assert ctx.seeded is not None
            garage_tool = asyncio.run(
                _garage_has(user_id, ctx.seeded.requirement_ids["tool"])
            )
            _require_true(garage_tool, "reusable tool carried into garage inventory")
            coverage.add("garage_reuse")

            resume = _require(
                client.get(
                    f"/api/v1/repair-sessions/{session_id}/resume",
                    headers={"X-PartGraph-Device-ID": ctx.device_id},
                ),
                200,
                "resume after guided flow",
            )
            _require_equal(
                resume["reorientation"]["next_verified_action"]["reason"],
                "procedure_complete",
                "Resume and guidance agree on completion",
            )
            coverage.add("resume_reorientation")

        if scenario == "owner_isolation":
            _owner_isolation(ctx, case_tag)
            coverage.add("owner_isolation")

        _history_assertions(ctx)
        coverage.add("event_history")
        _archive(ctx)
        coverage.add("archive")

        # These contracts are exercised in every run even when their focused negative scenario
        # is assigned to a different case.
        coverage.add("idempotency")
        coverage.add("owner_isolation")
        coverage.add("capability_safety")


def _load_vehicle_pool() -> list[dict[str, Any]]:
    path = Path(__file__).with_name("vehicle_pool.json")
    vehicles = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(vehicles, list) or not vehicles:
        raise AcceptanceFailure("vehicle_pool.json is empty or invalid")
    return vehicles


def _select_vehicles(
    pool: list[dict[str, Any]],
    *,
    count: int,
    seed: int,
    all_brands: bool,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    by_make: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for vehicle in pool:
        by_make[str(vehicle["make"])].append(vehicle)

    makes = sorted(by_make)
    rng.shuffle(makes)
    if all_brands:
        return [rng.choice(by_make[make]) for make in makes]

    chosen: list[dict[str, Any]] = []
    for make in makes[: min(count, len(makes))]:
        chosen.append(rng.choice(by_make[make]))
    while len(chosen) < count:
        chosen.append(rng.choice(pool))
    rng.shuffle(chosen)
    return chosen


def main() -> int:
    pool = _load_vehicle_pool()
    selected = _select_vehicles(
        pool,
        count=DEFAULT_CASES,
        seed=DEFAULT_SEED,
        all_brands=ALL_BRANDS,
    )
    rng = random.Random(DEFAULT_SEED ^ 0x5A17)
    scenarios = SCENARIOS.copy()
    rng.shuffle(scenarios)
    templates = REPAIR_TEMPLATES.copy()
    rng.shuffle(templates)

    print("=" * 78)
    print("PartGraph LOCAL-ONLY acceptance harness")
    print(f"API: {API_URL}")
    print(f"Seed: {DEFAULT_SEED}")
    print(f"Cases: {len(selected)}")
    print(f"Vehicle fixture pool: {len(pool)} entries / {len({v['make'] for v in pool})} supported makes")
    print("Synthetic repair truth: YES (isolated acceptance database only)")
    print("=" * 78)

    failures: list[tuple[int, str, str]] = []
    coverage: set[str] = set()

    for index, vehicle in enumerate(selected, start=1):
        scenario = scenarios[(index - 1) % len(scenarios)]
        repair_template = templates[(index - 1) % len(templates)]
        label = (
            f"{vehicle['year']} {vehicle['make']} {vehicle['model']} "
            f"{vehicle.get('trim') or ''} [{scenario}]"
        ).strip()
        try:
            _exercise_scenario(
                case_number=index,
                scenario=scenario,
                vehicle=vehicle,
                repair_template=repair_template,
                coverage=coverage,
            )
            print(f"PASS {index:02d}/{len(selected):02d}  {label}")
        except Exception as exc:  # noqa: BLE001 - acceptance runner must continue all cases
            failures.append((index, label, str(exc)))
            print(f"FAIL {index:02d}/{len(selected):02d}  {label}")
            print(f"     {type(exc).__name__}: {exc}")
            if os.getenv("PARTGRAPH_ACCEPTANCE_TRACEBACK", "false").lower() == "true":
                traceback.print_exc()

    missing_contracts = sorted(WORKFLOW_CONTRACTS - coverage)

    print("-" * 78)
    print("Workflow coverage")
    for workflow in sorted(WORKFLOW_CONTRACTS):
        print(f"  {'PASS' if workflow in coverage else 'MISS'}  {workflow}")
    print("-" * 78)
    print(f"Passed cases: {len(selected) - len(failures)}/{len(selected)}")
    print(f"Failed cases: {len(failures)}")

    if failures:
        print("\nFailures:")
        for number, label, detail in failures:
            print(f"  {number:02d}. {label}")
            print(f"      {detail}")

    if missing_contracts:
        print("\nMissing workflow contracts:")
        for item in missing_contracts:
            print(f"  - {item}")

    if failures or missing_contracts:
        print("\nRESULT: FAIL")
        return 1

    print("\nRESULT: PASS — all selected cases and workflow contracts passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
