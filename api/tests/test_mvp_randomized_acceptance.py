from __future__ import annotations

import hashlib
import json
import os
import random
import unittest
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import text

from partgraph.database import session_factory
from partgraph.identity.auth.models import User
from partgraph.identity.auth.service import set_user_context
from partgraph.identity.user_vehicle.models import UserVehicle
from partgraph.identity.vehicle.schemas import VehicleConfigurationInput
from partgraph.identity.vehicle.service import resolve_configuration
from partgraph.knowledge.canonical_claim_materialization import (
    materialize_verified_mechanical_claim_service,
)
from partgraph.knowledge.models import (
    CatalogSource,
    CatalogVerifiedEvidence,
    MechanicalClaim,
)
from partgraph.knowledge.repair_materialization_contract import (
    RepairDefinitionMaterializationCreate,
)
from partgraph.knowledge.repair_materialization_service import (
    materialize_repair_definition_service,
)
from partgraph.repair_experience.completion import _completion_view
from partgraph.repair_experience.guidance import (
    GuidanceActionUpdate,
    _guidance_view,
    update_action_progress,
)
from partgraph.repair_experience.readiness import (
    RepairReadinessUpdate,
    _readiness_view,
    update_repair_readiness,
)
from partgraph.repair_experience.repair_definition_binding import (
    RepairDefinitionBind,
    bind_repair_definition,
)
from partgraph.repair_experience.service import create_repair_session, event_history

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
SEED_ENV = "PARTGRAPH_RANDOMIZED_ACCEPTANCE_SEED"
DEFAULT_SEED = 20260917
CASE_COUNT = 20
REQUIREMENT_KINDS = (
    ("part", "replacement_required"),
    ("consumable", "consumed"),
    ("tool", "reusable"),
    ("equipment", "reusable"),
    ("workspace", "reusable"),
)


@dataclass(frozen=True)
class AcceptanceCase:
    case_number: int
    vehicle: dict[str, object]
    repair_key: str
    title: str
    requirements: list[dict[str, object]]
    actions: list[dict[str, object]]
    action_results: dict[str, str]
    readiness_order: list[str]
    transient_readiness_state: str | None


def _raw_sha(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _claim_payload(item: dict[str, object], *, requirement: bool) -> dict[str, object]:
    excluded = {"use_key"} if requirement else set()
    return {key: value for key, value in item.items() if key not in excluded}


def _build_cases(seed: int) -> list[AcceptanceCase]:
    rng = random.Random(seed)
    years = list(range(1996, 2027))
    rng.shuffle(years)
    cases: list[AcceptanceCase] = []

    for case_number in range(1, CASE_COUNT + 1):
        vehicle: dict[str, object] = {
            "year": years[case_number - 1],
            "market": "US",
            "make": f"AcceptanceMake{case_number:02d}",
            "model": f"AcceptanceModel{case_number:02d}",
            "trim": f"AcceptanceTrim{((case_number - 1) % 8) + 1:02d}",
        }
        requirement_count = rng.randint(1, 4)
        action_count = rng.randint(2, 5)

        requirements: list[dict[str, object]] = []
        for requirement_number in range(1, requirement_count + 1):
            category, fulfillment_mode = rng.choice(REQUIREMENT_KINDS)
            requirements.append(
                {
                    "use_key": f"case-{case_number:02d}-use-{requirement_number:02d}",
                    "requirement_key": (
                        f"{category}.phase9.acceptance_{case_number:02d}_{requirement_number:02d}"
                    ),
                    "category": category,
                    "display_name": (
                        f"Synthetic acceptance {category} "
                        f"{case_number:02d}-{requirement_number:02d}"
                    ),
                    "default_unit": "each",
                    "quantity": 1,
                    "unit": "each",
                    "necessity": "required",
                    "fulfillment_mode": fulfillment_mode,
                    "timing": "whole_repair",
                }
            )

        actions: list[dict[str, object]] = []
        action_results: dict[str, str] = {}
        previous_key: str | None = None
        for action_number in range(1, action_count + 1):
            action_key = f"case-{case_number:02d}-step-{action_number:02d}"
            requirement = rng.choice(requirements)
            forced_skip = case_number % 5 == 0 and action_number == action_count
            skippable = forced_skip or (action_number > 1 and rng.random() < 0.35)
            actions.append(
                {
                    "action_key": action_key,
                    "title": f"Synthetic acceptance step {case_number:02d}-{action_number:02d}",
                    "instruction": (
                        "Synthetic acceptance instruction used only to validate deterministic "
                        "PartGraph runtime behavior."
                    ),
                    "position": action_number - 1,
                    "skippable": skippable,
                    "prerequisite_action_keys": [] if previous_key is None else [previous_key],
                    "requirement_use_keys": [str(requirement["use_key"])],
                }
            )
            action_results[action_key] = (
                "skipped"
                if forced_skip or (skippable and rng.random() < 0.4)
                else "completed"
            )
            previous_key = action_key

        readiness_order = [str(item["requirement_key"]) for item in requirements]
        rng.shuffle(readiness_order)
        transient_state = None
        if case_number % 4 == 0:
            transient_state = "ordered"
        elif case_number % 6 == 0:
            transient_state = "unavailable"

        cases.append(
            AcceptanceCase(
                case_number=case_number,
                vehicle=vehicle,
                repair_key=f"phase9-synthetic-repair-{case_number:02d}",
                title=f"Phase 9 synthetic acceptance repair {case_number:02d}",
                requirements=requirements,
                actions=actions,
                action_results=action_results,
                readiness_order=readiness_order,
                transient_readiness_state=transient_state,
            )
        )

    rng.shuffle(cases)
    return cases


class FinalMvpRandomizedAcceptanceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")
        self.seed = int(os.environ.get(SEED_ENV, str(DEFAULT_SEED)))
        self.cases = _build_cases(self.seed)

    async def _run_case(self, case: AcceptanceCase) -> None:
        db = session_factory()
        try:
            now = datetime.now(UTC)
            suffix = uuid4().hex[:10]
            vehicle_input = VehicleConfigurationInput.model_validate(case.vehicle)
            configuration, resolution = await resolve_configuration(db, vehicle_input)
            self.assertEqual(resolution, "created")
            self.assertEqual(configuration.verification_status, "unverified")

            source = CatalogSource(
                id=uuid4(),
                source_key=f"phase9-random-{case.case_number:02d}-{suffix}",
                display_name="Phase 9 synthetic randomized acceptance source",
                source_class="oem_service",
                license_status="approved",
                automation_allowed=False,
                notes="Synthetic ephemeral acceptance evidence; not automotive repair truth.",
            )
            identity_evidence = CatalogVerifiedEvidence(
                id=uuid4(),
                staging_record_id=uuid4(),
                candidate_type="mechanical_claim_candidate",
                verified_payload={"mechanical_claim": dict(case.vehicle)},
                vehicle_identity={"vehicle_configuration_id": str(configuration.id)},
                source_name=source.source_key,
                source_type="synthetic_acceptance",
                source_record_id=f"phase9-random:{case.case_number:02d}:{suffix}:identity",
                source_url="https://example.invalid/partgraph/phase9-randomized-acceptance",
                raw_sha256=_raw_sha(case.vehicle),
                fetched_at=now,
                provenance={
                    "fixture": "phase9-randomized-acceptance",
                    "seed": self.seed,
                    "case": case.case_number,
                },
                extraction_method="deterministic_synthetic_acceptance",
                promoted_by="phase9-randomized-reviewer",
            )
            identity_claim = MechanicalClaim(
                id=uuid4(),
                source_id=source.id,
                verified_evidence_id=identity_evidence.id,
                vehicle_configuration_id=configuration.id,
                claim_domain="vehicle_identity",
                claim_risk="normal",
                normalized_key=f"phase9.random.{case.case_number:02d}.{suffix}.identity",
                claim_payload=dict(case.vehicle),
                explicit_claim=True,
                exact_applicability=True,
                promotion_state="verified",
                reviewed_at=now,
                reviewed_by="phase9-randomized-curator",
            )
            db.add_all([source, identity_evidence, identity_claim])
            await db.flush()

            await db.execute(text("SET LOCAL ROLE partgraph_materializer"))
            identity_publication = await materialize_verified_mechanical_claim_service(
                db,
                claim_id=identity_claim.id,
                actor="phase9-randomized-curator",
                idempotency_key=f"phase9.random.{case.case_number:02d}.{suffix}.identity",
            )
            await db.execute(text("RESET ROLE"))
            self.assertEqual(identity_publication.record_id, configuration.id)
            await db.refresh(configuration)
            self.assertEqual(configuration.verification_status, "verified")

            requirement_claim_ids: dict[str, UUID] = {}
            action_claim_ids: dict[str, UUID] = {}
            for claim_domain, key_name, requirement, items, target in (
                (
                    "repair_requirement",
                    "use_key",
                    True,
                    case.requirements,
                    requirement_claim_ids,
                ),
                (
                    "repair_procedure",
                    "action_key",
                    False,
                    case.actions,
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
                        vehicle_identity={"vehicle_configuration_id": str(configuration.id)},
                        source_name=source.source_key,
                        source_type="synthetic_acceptance",
                        source_record_id=(
                            f"phase9-random:{case.case_number:02d}:{suffix}:"
                            f"{claim_domain}:{item_key}"
                        ),
                        source_url="https://example.invalid/partgraph/phase9-randomized-acceptance",
                        raw_sha256=_raw_sha(payload),
                        fetched_at=now,
                        provenance={
                            "fixture": "phase9-randomized-acceptance",
                            "seed": self.seed,
                            "case": case.case_number,
                        },
                        extraction_method="deterministic_synthetic_acceptance",
                        promoted_by="phase9-randomized-reviewer",
                    )
                    claim = MechanicalClaim(
                        id=uuid4(),
                        source_id=source.id,
                        verified_evidence_id=evidence.id,
                        vehicle_configuration_id=configuration.id,
                        claim_domain=claim_domain,
                        claim_risk="normal",
                        normalized_key=(
                            f"phase9.random.{case.case_number:02d}.{suffix}."
                            f"{claim_domain}.{item_key}"
                        ),
                        repair_key=case.repair_key,
                        claim_payload=payload,
                        explicit_claim=True,
                        exact_applicability=True,
                        promotion_state="verified",
                        reviewed_at=now,
                        reviewed_by="phase9-randomized-curator",
                    )
                    db.add_all([evidence, claim])
                    target[item_key] = claim.id
            await db.flush()

            request = RepairDefinitionMaterializationCreate(
                vehicle_configuration_id=configuration.id,
                repair_key=case.repair_key,
                title=case.title,
                capability_policy_key="diy_supported",
                operations=[],
                requirements=[
                    {
                        **item,
                        "supporting_claim_ids": [
                            requirement_claim_ids[str(item["use_key"])]
                        ],
                    }
                    for item in case.requirements
                ],
                actions=[
                    {
                        **item,
                        "supporting_claim_ids": [
                            action_claim_ids[str(item["action_key"])]
                        ],
                    }
                    for item in case.actions
                ],
            )
            await db.execute(text("SET LOCAL ROLE partgraph_materializer"))
            repair_publication = await materialize_repair_definition_service(
                db,
                request=request,
                actor="phase9-randomized-curator",
                idempotency_key=f"phase9.random.{case.case_number:02d}.{suffix}.repair",
            )
            await db.execute(text("RESET ROLE"))

            user = User(
                id=uuid4(),
                email=f"phase9-random-{case.case_number:02d}-{suffix}@example.invalid",
                username=f"p9rand_{case.case_number:02d}_{suffix[:8]}",
                password_hash="phase9-randomized-acceptance",
                role="owner",
                is_active=True,
            )
            user_vehicle = UserVehicle(
                id=uuid4(),
                user_id=user.id,
                canonical_configuration_id=configuration.id,
                nickname=f"Synthetic case {case.case_number:02d}",
                identity_source="manual",
                identity_resolution="matched",
                identity_snapshot=dict(case.vehicle),
            )
            db.add_all([user, user_vehicle])
            await db.flush()

            await db.execute(text("SET LOCAL ROLE partgraph_app"))
            await set_user_context(db, user.id)
            device_id = uuid4()
            bundle = await create_repair_session(
                db,
                user_id=user.id,
                user_vehicle_id=user_vehicle.id,
                title=case.title,
                device_id=device_id,
                idempotency_key=f"p9rand_{case.case_number:02d}_{suffix}_session",
            )
            session_id = bundle.repair_session.id

            binding = await bind_repair_definition(
                session_id,
                RepairDefinitionBind(repair_key=case.repair_key),
                user,
                db,
                device_header=str(device_id),
            )
            self.assertEqual(binding.binding_state, "bound")
            self.assertEqual(
                binding.repair_definition_id,
                repair_publication.repair_definition_id,
            )

            readiness = await _readiness_view(
                db,
                user_id=user.id,
                repair_session=bundle.repair_session,
            )
            self.assertEqual(readiness.summary.total, len(case.requirements))
            self.assertEqual(readiness.summary.missing, len(case.requirements))
            self.assertEqual(readiness.summary.blocked, len(case.requirements))

            requirement_by_use = {
                str(item["use_key"]): str(item["requirement_key"])
                for item in case.requirements
            }
            first_use_key = str(case.actions[0]["requirement_use_keys"][0])
            blocked = await _guidance_view(
                db,
                user_id=user.id,
                session_id=session_id,
                include_plan=False,
            )
            self.assertEqual(blocked.status, "inventory_blocked")
            self.assertIsNotNone(blocked.current_action)
            assert blocked.current_action is not None
            self.assertEqual(blocked.current_action.action_key, case.actions[0]["action_key"])
            self.assertIn(
                requirement_by_use[first_use_key],
                {item.requirement_key for item in blocked.current_action.inventory_blockers},
            )

            readiness_events = 0
            readiness_by_key = {item.requirement_key: item for item in readiness.requirements}
            if case.transient_readiness_state is not None:
                transient_key = case.readiness_order[0]
                transient_item = readiness_by_key[transient_key]
                await update_repair_readiness(
                    session_id,
                    transient_item.requirement_definition_id,
                    RepairReadinessUpdate(
                        readiness_state=case.transient_readiness_state,
                    ),
                    user,
                    db,
                    device_header=str(device_id),
                    idempotency_header=(
                        f"p9rand_{case.case_number:02d}_{suffix}_transient"
                    ),
                )
                readiness_events += 1

            for readiness_number, requirement_key in enumerate(case.readiness_order, start=1):
                item = readiness_by_key[requirement_key]
                readiness = await update_repair_readiness(
                    session_id,
                    item.requirement_definition_id,
                    RepairReadinessUpdate(readiness_state="have"),
                    user,
                    db,
                    device_header=str(device_id),
                    idempotency_header=(
                        f"p9rand_{case.case_number:02d}_{suffix}_ready_{readiness_number:02d}"
                    ),
                )
                readiness_events += 1

            self.assertEqual(readiness.summary.ready, len(case.requirements))
            self.assertEqual(readiness.summary.blocked, 0)

            expected_completed = 0
            expected_skipped = 0
            for action_number, expected_action in enumerate(case.actions, start=1):
                guidance = await _guidance_view(
                    db,
                    user_id=user.id,
                    session_id=session_id,
                    include_plan=False,
                )
                self.assertEqual(guidance.status, "action_available")
                self.assertIsNotNone(guidance.current_action)
                assert guidance.current_action is not None
                self.assertEqual(
                    guidance.current_action.action_key,
                    expected_action["action_key"],
                )
                target_state = case.action_results[str(expected_action["action_key"])]
                if target_state == "skipped":
                    self.assertTrue(guidance.current_action.skippable)
                    expected_skipped += 1
                else:
                    expected_completed += 1
                await update_action_progress(
                    session_id,
                    guidance.current_action.action_id,
                    GuidanceActionUpdate(progress_state=target_state),
                    user,
                    db,
                    device_header=str(device_id),
                    idempotency_header=(
                        f"p9rand_{case.case_number:02d}_{suffix}_action_{action_number:02d}"
                    ),
                )

            final_guidance = await _guidance_view(
                db,
                user_id=user.id,
                session_id=session_id,
                include_plan=False,
            )
            self.assertEqual(final_guidance.status, "procedure_complete")
            self.assertTrue(final_guidance.procedure_complete)
            self.assertEqual(final_guidance.summary.completed, expected_completed)
            self.assertEqual(final_guidance.summary.skipped, expected_skipped)
            self.assertEqual(final_guidance.summary.pending, 0)
            self.assertEqual(final_guidance.summary.blocked, 0)

            completion = await _completion_view(
                db,
                user_id=user.id,
                session_id=session_id,
            )
            self.assertEqual(
                completion.completion_status,
                "fully_mechanically_complete",
            )
            self.assertTrue(completion.fully_mechanically_complete)
            self.assertFalse(completion.downstream_required_pending)
            self.assertFalse(completion.unsupported_or_professional_downstream_pending)

            history = await event_history(
                db,
                user_id=user.id,
                session_id=session_id,
                after_sequence=0,
                limit=100,
            )
            self.assertEqual(
                sum(item.event_type == "readiness_state_changed" for item in history.items),
                readiness_events,
            )
            self.assertEqual(
                sum(
                    item.event_type == "procedure_action_state_changed"
                    for item in history.items
                ),
                len(case.actions),
            )
        finally:
            await db.rollback()
            await db.close()

    async def test_seeded_randomized_runtime_acceptance(self) -> None:
        self.assertEqual(len(self.cases), CASE_COUNT)
        self.assertEqual(
            len(
                {
                    (
                        item.vehicle["year"],
                        item.vehicle["make"],
                        item.vehicle["model"],
                        item.vehicle["trim"],
                    )
                    for item in self.cases
                }
            ),
            CASE_COUNT,
        )
        self.assertEqual(len({item.vehicle["make"] for item in self.cases}), CASE_COUNT)
        self.assertEqual(len({item.vehicle["model"] for item in self.cases}), CASE_COUNT)
        self.assertGreaterEqual(len({item.vehicle["trim"] for item in self.cases}), 8)
        self.assertEqual(len({item.vehicle["year"] for item in self.cases}), CASE_COUNT)
        self.assertGreater(
            sum(
                result == "skipped"
                for item in self.cases
                for result in item.action_results.values()
            ),
            0,
        )

        print(
            "PartGraph Phase 9 randomized acceptance "
            f"| seed={self.seed} | cases={CASE_COUNT}"
        )
        for ordinal, case in enumerate(self.cases, start=1):
            with self.subTest(
                case=case.case_number,
                vehicle=(
                    case.vehicle["year"],
                    case.vehicle["make"],
                    case.vehicle["model"],
                    case.vehicle["trim"],
                ),
            ):
                await self._run_case(case)
            print(
                f"PASS {ordinal:02d}/{CASE_COUNT} "
                f"case={case.case_number:02d} "
                f"{case.vehicle['year']} {case.vehicle['make']} "
                f"{case.vehicle['model']} {case.vehicle['trim']}"
            )


if __name__ == "__main__":
    unittest.main()
