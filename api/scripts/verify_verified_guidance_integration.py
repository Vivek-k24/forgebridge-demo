from __future__ import annotations

import argparse
import asyncio
import hashlib
import http.cookiejar
import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from sqlalchemy import select, text
from sqlalchemy.engine import make_url

from partgraph.database import session_factory
from partgraph.identity.vehicle.models import VehicleConfiguration
from partgraph.knowledge.models import (
    CatalogSource,
    CatalogVerifiedEvidence,
    MechanicalClaim,
    RepairDefinition,
)
from partgraph.knowledge.repair_materialization_contract import (
    RepairDefinitionMaterializationCreate,
)
from partgraph.knowledge.repair_materialization_service import (
    materialize_repair_definition_service,
)

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
BASE_URL = os.environ.get("PARTGRAPH_VERIFIED_GUIDANCE_URL", "http://127.0.0.1:8000").rstrip("/")
ORIGIN = BASE_URL
CSRF_HEADER = "X-PartGraph-CSRF"
CSRF_VALUE = "1"
API_VERSION = "v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
PRIMARY_BUNDLE_PATH = (
    REPO_ROOT / "api" / "data" / "reference" / "primary_reference_bundle_v1.json"
)
DEFAULT_STATE_PATH = Path("/tmp/phase9-verified-guidance.json")


def _primary_reference_repair() -> tuple[UUID, Path]:
    bundle = json.loads(PRIMARY_BUNDLE_PATH.read_text(encoding="utf-8"))
    manifest_path = (REPO_ROOT / str(bundle["repair_manifest"])).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    repair_entry = next(
        item
        for item in manifest["repairs"]
        if item["repair_key"] == "engine-oil-filter-change"
    )
    return (
        UUID(str(manifest["vehicle_configuration_id"])),
        manifest_path.parent / str(repair_entry["path"]),
    )


REFERENCE_VEHICLE_ID, REFERENCE_REPAIR_PATH = _primary_reference_repair()


def _database_connection_string() -> str:
    raw = os.environ.get(DATABASE_URL_ENV)
    if not raw:
        raise RuntimeError(f"{DATABASE_URL_ENV} is required")
    url = make_url(raw)
    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("Verified-guidance integration requires PostgreSQL")
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def _claim_payload(item: dict[str, object], *, requirement: bool) -> dict[str, object]:
    excluded = {"source_pages", "use_key"} if requirement else {"source_pages"}
    return {key: value for key, value in item.items() if key not in excluded}


def _raw_sha(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _vehicle_selection(vehicle: VehicleConfiguration) -> dict[str, object]:
    selection: dict[str, object] = {
        "year": vehicle.year,
        "market": vehicle.market,
        "make": vehicle.make,
        "model": vehicle.model,
    }
    for field in (
        "trim",
        "generation",
        "body_style",
        "engine",
        "transmission",
        "drivetrain",
    ):
        value = getattr(vehicle, field)
        if value is not None:
            selection[field] = value
    return selection


async def seed_verified_repair(state_path: Path) -> None:
    reference = json.loads(REFERENCE_REPAIR_PATH.read_text(encoding="utf-8"))
    if reference["vehicle_configuration_id"] != str(REFERENCE_VEHICLE_ID):
        raise AssertionError("reference repair vehicle configuration changed unexpectedly")
    if reference["repair_key"] != "engine-oil-filter-change":
        raise AssertionError("reference repair key changed unexpectedly")

    async with session_factory() as db:
        async with db.begin():
            vehicle = await db.get(VehicleConfiguration, REFERENCE_VEHICLE_ID)
            if vehicle is None:
                raise AssertionError("primary reference vehicle configuration is missing")
            if vehicle.verification_status != "verified":
                raise AssertionError("primary reference vehicle configuration is not verified")

            existing = await db.scalar(
                select(RepairDefinition).where(
                    RepairDefinition.vehicle_configuration_id == REFERENCE_VEHICLE_ID,
                    RepairDefinition.repair_key == reference["repair_key"],
                    RepairDefinition.status == "verified",
                )
            )
            if existing is not None:
                raise AssertionError(
                    "verified-guidance integration expects a fresh database without the reference repair"
                )

            source = CatalogSource(
                id=uuid4(),
                source_key="phase9-verified-guidance-oem",
                display_name="Phase 9 verified-guidance OEM service evidence",
                source_class="oem_service",
                license_status="approved",
                automation_allowed=False,
            )
            db.add(source)
            await db.flush()

            now = datetime.now(UTC)
            requirement_claim_ids: dict[str, UUID] = {}
            action_claim_ids: dict[str, UUID] = {}

            for claim_domain, key_name, requirement, items, target in (
                (
                    "repair_requirement",
                    "use_key",
                    True,
                    reference["requirements"],
                    requirement_claim_ids,
                ),
                (
                    "repair_procedure",
                    "action_key",
                    False,
                    reference["actions"],
                    action_claim_ids,
                ),
            ):
                for item in items:
                    item_key = str(item[key_name])
                    payload = _claim_payload(item, requirement=requirement)
                    evidence = CatalogVerifiedEvidence(
                        id=uuid4(),
                        staging_record_id=uuid4(),
                        candidate_type="mechanical_claim_candidate",
                        verified_payload={"mechanical_claim": payload},
                        vehicle_identity={
                            "vehicle_configuration_id": str(REFERENCE_VEHICLE_ID)
                        },
                        source_name=source.source_key,
                        source_type="oem_service",
                        source_record_id=f"phase9-guidance:{claim_domain}:{item_key}",
                        source_url=(
                            "https://example.invalid/phase9-verified-guidance/"
                            f"{claim_domain}/{item_key}"
                        ),
                        raw_sha256=_raw_sha(payload),
                        fetched_at=now,
                        provenance={
                            "fixture": "phase9-verified-guidance",
                            "source_pages": item.get("source_pages", []),
                        },
                        extraction_method="reference_fixture",
                        promoted_by="phase9-guidance-reviewer",
                    )
                    claim = MechanicalClaim(
                        id=uuid4(),
                        source_id=source.id,
                        verified_evidence_id=evidence.id,
                        vehicle_configuration_id=REFERENCE_VEHICLE_ID,
                        claim_domain=claim_domain,
                        claim_risk="normal",
                        normalized_key=f"phase9.guidance.{claim_domain}.{item_key}",
                        repair_key=reference["repair_key"],
                        claim_payload=payload,
                        explicit_claim=True,
                        exact_applicability=True,
                        promotion_state="verified",
                        reviewed_at=now,
                        reviewed_by="phase9-guidance-curator",
                    )
                    db.add_all([evidence, claim])
                    target[item_key] = claim.id
            await db.flush()

            request = RepairDefinitionMaterializationCreate(
                vehicle_configuration_id=REFERENCE_VEHICLE_ID,
                repair_key=reference["repair_key"],
                title=reference["title"],
                capability_policy_key=reference["capability_policy_key"],
                operations=reference["operations"],
                requirements=[
                    {
                        **{
                            key: value
                            for key, value in item.items()
                            if key != "source_pages"
                        },
                        "supporting_claim_ids": [
                            requirement_claim_ids[str(item["use_key"])]
                        ],
                    }
                    for item in reference["requirements"]
                ],
                actions=[
                    {
                        **{
                            key: value
                            for key, value in item.items()
                            if key != "source_pages"
                        },
                        "supporting_claim_ids": [
                            action_claim_ids[str(item["action_key"])]
                        ],
                    }
                    for item in reference["actions"]
                ],
            )

            await db.execute(text("SET LOCAL ROLE partgraph_materializer"))
            publication = await materialize_repair_definition_service(
                db,
                request=request,
                actor="phase9-guidance-curator",
                idempotency_key="phase9-verified-guidance-materialization",
            )

            state = {
                "vehicle_configuration_id": str(REFERENCE_VEHICLE_ID),
                "vehicle_selection": _vehicle_selection(vehicle),
                "repair_key": reference["repair_key"],
                "repair_definition_id": str(publication.repair_definition_id),
                "expected_action_keys": [
                    str(item["action_key"]) for item in reference["actions"]
                ],
                "expected_requirement_count": len(reference["requirements"]),
            }

    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "Seeded reviewed OEM-style evidence and materialized verified repair definition "
        f"{state['repair_definition_id']}."
    )


class HttpResponse:
    def __init__(self, status: int, headers: Any, body: bytes) -> None:
        self.status = status
        self.headers = headers
        self.body = body

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )


def _request(
    opener: urllib.request.OpenerDirector,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    csrf: bool = False,
    device_id: str | None = None,
    idempotency_key: str | None = None,
) -> HttpResponse:
    headers = {"Origin": ORIGIN}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    if csrf:
        headers[CSRF_HEADER] = CSRF_VALUE
    if device_id is not None:
        headers["X-PartGraph-Device-ID"] = device_id
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key

    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with opener.open(request, timeout=10) as response:
            return HttpResponse(response.status, response.headers, response.read())
    except urllib.error.HTTPError as exc:
        return HttpResponse(exc.code, exc.headers, exc.read())


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _require_api(response: HttpResponse) -> None:
    _require(
        response.headers.get("X-PartGraph-API-Version") == API_VERSION,
        f"missing or wrong API version on HTTP {response.status}",
    )


def _assert_claims_verified(claim_ids: list[str]) -> None:
    if not claim_ids:
        raise AssertionError("guidance returned no supporting claims")

    with psycopg.connect(
        _database_connection_string(),
        row_factory=dict_row,
    ) as connection:
        rows = connection.execute(
            """
            SELECT
                mc.id::text AS claim_id,
                mc.promotion_state,
                mc.explicit_claim,
                mc.exact_applicability,
                mc.claim_domain,
                cs.license_status,
                cve.id IS NOT NULL AS has_verified_evidence
            FROM mechanical_claims mc
            JOIN catalog_sources cs ON cs.id = mc.source_id
            JOIN catalog_verified_evidence cve ON cve.id = mc.verified_evidence_id
            WHERE mc.id = ANY(%s::uuid[])
            ORDER BY mc.id
            """,
            (claim_ids,),
        ).fetchall()

    _require(len(rows) == len(set(claim_ids)), "one or more guidance claims are missing")
    for row in rows:
        _require(row["promotion_state"] == "verified", "guidance used a non-verified claim")
        _require(bool(row["explicit_claim"]), "guidance used an implicit claim")
        _require(bool(row["exact_applicability"]), "guidance used a non-exact claim")
        _require(row["claim_domain"] == "repair_procedure", "guidance used the wrong claim domain")
        _require(row["license_status"] == "approved", "guidance used an unapproved source")
        _require(bool(row["has_verified_evidence"]), "guidance claim lost verified evidence")


def _set_claim_state(claim_id: str, state: str) -> None:
    with psycopg.connect(_database_connection_string()) as connection:
        changed = connection.execute(
            """
            UPDATE mechanical_claims
            SET promotion_state = %s
            WHERE id = %s::uuid
            """,
            (state, claim_id),
        ).rowcount
        if changed != 1:
            raise AssertionError(f"expected to update one claim, updated {changed}")


def verify_http_guidance(state_path: Path) -> None:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    opener = _opener()
    device_id = str(uuid4())

    ready = _request(opener, "/api/v1/health/ready")
    _require(ready.status == 200, f"readiness returned {ready.status}")
    _require_api(ready)
    _require(ready.json().get("database") == "ready", "database is not ready")

    registration = _request(
        opener,
        "/api/v1/auth/register",
        method="POST",
        csrf=True,
        payload={
            "email": "phase9-verified-guidance@example.com",
            "username": "phase9_guidance",
            "password": "Phase9-" + uuid4().hex + "-Aa1!",
        },
    )
    _require(registration.status == 200, f"registration returned {registration.status}")

    vehicle_create = _request(
        opener,
        "/api/v1/user-vehicles/manual",
        method="POST",
        csrf=True,
        payload={
            "nickname": "Verified guidance reference vehicle",
            "selection": state["vehicle_selection"],
        },
    )
    _require(vehicle_create.status == 201, f"vehicle create returned {vehicle_create.status}")
    vehicle = vehicle_create.json()
    _require(
        vehicle.get("canonical_configuration_id") == state["vehicle_configuration_id"],
        "manual vehicle did not resolve to the exact reviewed configuration",
    )
    _require(vehicle.get("identity_resolution") == "matched", "vehicle did not resolve exactly")

    session_create = _request(
        opener,
        "/api/v1/repair-sessions",
        method="POST",
        csrf=True,
        device_id=device_id,
        idempotency_key="phase9_guidance_session",
        payload={
            "user_vehicle_id": vehicle["id"],
            "title": "Phase 9 verified guidance",
        },
    )
    _require(session_create.status == 201, f"repair session create returned {session_create.status}")
    session_id = session_create.json()["session"]["id"]

    options = _request(opener, f"/api/v1/repair-sessions/{session_id}/repair-options")
    _require(options.status == 200, f"repair options returned {options.status}")
    options_payload = options.json()
    _require(options_payload.get("vehicle_resolution") == "exact", "repair vehicle is unresolved")
    matching = [
        item
        for item in options_payload.get("options", [])
        if item.get("repair_key") == state["repair_key"]
    ]
    _require(len(matching) == 1, "materialized verified repair is not uniquely available")
    _require(
        matching[0].get("repair_definition_id") == state["repair_definition_id"],
        "repair option does not reference the materialized definition",
    )

    binding = _request(
        opener,
        f"/api/v1/repair-sessions/{session_id}/repair-definition",
        method="PUT",
        csrf=True,
        device_id=device_id,
        payload={"repair_key": state["repair_key"]},
    )
    _require(binding.status == 200, f"repair binding returned {binding.status}")
    _require(
        binding.json().get("repair_definition_id") == state["repair_definition_id"],
        "bound repair definition mismatch",
    )

    readiness = _request(opener, f"/api/v1/repair-sessions/{session_id}/readiness")
    _require(readiness.status == 200, f"readiness returned {readiness.status}")
    readiness_payload = readiness.json()
    _require(
        readiness_payload.get("summary", {}).get("total") == state["expected_requirement_count"],
        "verified requirement manifest count mismatch",
    )

    plan = _request(opener, f"/api/v1/repair-sessions/{session_id}/guidance/plan")
    _require(plan.status == 200, f"guidance plan returned {plan.status}")
    plan_payload = plan.json()
    _require(plan_payload.get("definition_status") == "verified", "guidance definition is not verified")
    _require(plan_payload.get("status") == "inventory_blocked", "initial guidance should be inventory-blocked")
    actions = plan_payload.get("actions", [])
    action_keys = [item.get("action_key") for item in actions]
    _require(
        action_keys == state["expected_action_keys"],
        f"verified action order mismatch: {action_keys}",
    )

    supporting_claim_ids = sorted(
        {
            str(claim_id)
            for action in actions
            for claim_id in action.get("supporting_claim_ids", [])
        }
    )
    _assert_claims_verified(supporting_claim_ids)

    required = [
        item
        for item in readiness_payload.get("requirements", [])
        if item.get("necessity") == "required"
    ]
    _require(bool(required), "readiness returned no required items")
    for index, item in enumerate(required, start=1):
        updated = _request(
            opener,
            (
                f"/api/v1/repair-sessions/{session_id}/readiness/"
                f"{item['requirement_definition_id']}"
            ),
            method="PUT",
            csrf=True,
            device_id=device_id,
            idempotency_key=f"phase9_ready_{index:02d}",
            payload={"readiness_state": "have"},
        )
        _require(updated.status == 200, f"readiness update {index} returned {updated.status}")

    guidance = _request(opener, f"/api/v1/repair-sessions/{session_id}/guidance")
    _require(guidance.status == 200, f"unblocked guidance returned {guidance.status}")
    guidance_payload = guidance.json()
    _require(guidance_payload.get("status") == "action_available", "guidance did not unblock")
    current = guidance_payload.get("current_action")
    _require(current is not None, "guidance has no current verified action")
    _require(current.get("action_key") == "prepare-access", "unexpected first verified action")
    _require(not current.get("inventory_blockers"), "current action still has inventory blockers")

    revoked_claim_id = str(current["supporting_claim_ids"][0])
    _set_claim_state(revoked_claim_id, "needs_review")
    try:
        failed = _request(opener, f"/api/v1/repair-sessions/{session_id}/guidance")
        _require(failed.status == 500, f"revoked evidence guidance returned {failed.status}")
        error = failed.json().get("error", {})
        _require(
            error.get("code") == "REPAIR_PROCEDURE_INTEGRITY_ERROR",
            f"revoked evidence did not fail closed: {error.get('code')}",
        )
    finally:
        _set_claim_state(revoked_claim_id, "verified")

    recovered = _request(opener, f"/api/v1/repair-sessions/{session_id}/guidance")
    _require(recovered.status == 200, f"restored guidance returned {recovered.status}")
    _require(recovered.json().get("status") == "action_available", "guidance did not recover")

    print(
        "Verified-guidance integration passed: reviewed evidence -> restricted materialization -> "
        "exact vehicle binding -> readiness -> provenance-backed guidance -> fail-closed claim "
        "revocation -> recovery."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("seed", "verify"))
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    args = parser.parse_args()

    if args.mode == "seed":
        asyncio.run(seed_verified_repair(args.state))
    else:
        verify_http_guidance(args.state)


if __name__ == "__main__":
    main()
