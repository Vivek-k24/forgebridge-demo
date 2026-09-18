from __future__ import annotations

import hashlib
import json
import os
import unittest
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select, text

from partgraph.database import session_factory
from partgraph.errors import PartGraphError
from partgraph.identity.auth.models import User
from partgraph.identity.auth.service import set_user_context
from partgraph.identity.user_vehicle.models import UserVehicle
from partgraph.identity.vehicle.models import VehicleConfiguration
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
from partgraph.knowledge.support_boundaries import (
    COMPUTER_SERVICE_BOUNDARY_ACTION_KEY,
    COMPUTER_SERVICE_BOUNDARY_CODE,
    COMPUTER_SERVICE_BOUNDARY_MESSAGE,
)
from partgraph.repair_experience.completion import _completion_view
from partgraph.repair_experience.guidance import (
    GuidanceActionUpdate,
    _guidance_view,
    update_action_progress,
)
from partgraph.repair_experience.models import (
    RepairProcedureActionState,
    RepairSessionEvent,
)
from partgraph.repair_experience.repair_definition_binding import (
    RepairDefinitionBind,
    bind_repair_definition,
)
from partgraph.repair_experience.service import create_repair_session

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"


def _sha(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


class MvpUnsupportedComputerBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def _cleanup_db(self) -> None:
        if hasattr(self, "transaction") and self.transaction.is_active:
            await self.transaction.rollback()
        if hasattr(self, "db"):
            await self.db.close()

    async def asyncSetUp(self) -> None:
        if DATABASE_URL_ENV not in os.environ:
            raise unittest.SkipTest(f"{DATABASE_URL_ENV} is not configured")

        self.db = session_factory()
        self.transaction = await self.db.begin()
        self.addAsyncCleanup(self._cleanup_db)

        suffix = uuid4().hex[:12]
        vehicle_id = uuid4()
        source_id = uuid4()
        now = datetime.now(UTC)
        self.repair_key = f"fixture.computer-boundary-{suffix}"

        vehicle = VehicleConfiguration(
            id=vehicle_id,
            identity_hash=hashlib.sha256(f"vehicle:{suffix}".encode()).hexdigest(),
            base_identity_hash=hashlib.sha256(f"base:{suffix}".encode()).hexdigest(),
            year=2026,
            market="test",
            make="Fixture",
            model="Boundary",
            trim="Synthetic",
            identity_source="fixture",
            verification_status="verified",
        )
        source = CatalogSource(
            id=source_id,
            source_key=f"computer-boundary-{suffix}",
            display_name="Synthetic computer-boundary verification source",
            source_class="oem_service",
            license_status="approved",
            automation_allowed=False,
        )
        self.user = User(
            id=uuid4(),
            email=f"computer-boundary-{suffix}@example.invalid",
            username=f"boundary_{suffix}",
            password_hash="synthetic-boundary-fixture",
            role="owner",
            is_active=True,
        )
        self.user_vehicle = UserVehicle(
            id=uuid4(),
            user_id=self.user.id,
            canonical_configuration_id=vehicle_id,
            nickname="Synthetic boundary vehicle",
            identity_source="manual",
            identity_resolution="matched",
            identity_snapshot={
                "year": 2026,
                "market": "test",
                "make": "Fixture",
                "model": "Boundary",
                "trim": "Synthetic",
                "body_style": None,
                "engine": None,
                "transmission": None,
                "drivetrain": None,
            },
        )
        self.db.add_all([vehicle, source, self.user, self.user_vehicle])
        await self.db.flush()

        actions = [
            {
                "action_key": "install-physical-component",
                "title": "Install physical component",
                "instruction": "Install the synthetic physical component.",
                "position": 0,
                "skippable": False,
            },
            {
                "action_key": COMPUTER_SERVICE_BOUNDARY_ACTION_KEY,
                "title": "Required computer-dependent service",
                "instruction": "Use a manufacturer service tool to initialize the component.",
                "position": 1,
                "skippable": False,
                "prerequisite_action_keys": ["install-physical-component"],
            },
        ]

        claim_ids = {}
        for action in actions:
            payload = dict(action)
            evidence = CatalogVerifiedEvidence(
                id=uuid4(),
                staging_record_id=uuid4(),
                candidate_type="mechanical_claim_candidate",
                verified_payload={"mechanical_claim": payload},
                vehicle_identity={"vehicle_configuration_id": str(vehicle_id)},
                source_name=source.source_key,
                source_type="oem_service",
                source_record_id=f"boundary:{action['action_key']}",
                source_url=(
                    "https://example.invalid/computer-boundary/"
                    f"{action['action_key']}"
                ),
                raw_sha256=_sha(payload),
                fetched_at=now,
                provenance={"fixture": "phase9-unsupported-computer-boundary"},
                extraction_method="synthetic_fixture",
                promoted_by="phase9-boundary-reviewer",
            )
            claim = MechanicalClaim(
                id=uuid4(),
                source_id=source.id,
                verified_evidence_id=evidence.id,
                vehicle_configuration_id=vehicle_id,
                claim_domain="repair_procedure",
                claim_risk="normal",
                normalized_key=f"fixture.boundary.{action['action_key']}",
                repair_key=self.repair_key,
                claim_payload=payload,
                explicit_claim=True,
                exact_applicability=True,
                promotion_state="verified",
                reviewed_at=now,
                reviewed_by="phase9-boundary-curator",
            )
            self.db.add_all([evidence, claim])
            claim_ids[str(action["action_key"])] = claim.id
        await self.db.flush()

        request = RepairDefinitionMaterializationCreate(
            vehicle_configuration_id=vehicle_id,
            repair_key=self.repair_key,
            title="Synthetic repair with required computer boundary",
            capability_policy_key="diy_supported",
            operations=[],
            requirements=[],
            actions=[
                {
                    **action,
                    "supporting_claim_ids": [claim_ids[str(action["action_key"])]],
                }
                for action in actions
            ],
        )

        await self.db.execute(text("SET LOCAL ROLE partgraph_materializer"))
        publication = await materialize_repair_definition_service(
            self.db,
            request=request,
            actor="phase9-boundary-curator",
            idempotency_key=f"phase9:boundary:{suffix}",
        )
        self.repair_definition_id = publication.repair_definition_id

        await self.db.execute(text("RESET ROLE"))
        await self.db.execute(text("SET LOCAL ROLE partgraph_app"))
        await set_user_context(self.db, self.user.id)
        self.device_id = uuid4()

    async def test_computer_service_boundary_is_terminal_and_non_completable(self) -> None:
        bundle = await create_repair_session(
            self.db,
            user_id=self.user.id,
            user_vehicle_id=self.user_vehicle.id,
            title="Synthetic computer-boundary repair",
            device_id=self.device_id,
            idempotency_key="phase9_boundary_session",
        )
        session_id = bundle.repair_session.id

        binding = await bind_repair_definition(
            session_id,
            RepairDefinitionBind(repair_key=self.repair_key),
            self.user,
            self.db,
            device_header=str(self.device_id),
        )
        self.assertEqual(binding.binding_state, "bound")
        self.assertEqual(binding.repair_definition_id, self.repair_definition_id)

        guidance = await _guidance_view(
            self.db,
            user_id=self.user.id,
            session_id=session_id,
            include_plan=False,
        )
        self.assertEqual(guidance.status, "action_available")
        self.assertIsNotNone(guidance.current_action)
        assert guidance.current_action is not None
        self.assertEqual(
            guidance.current_action.action_key,
            "install-physical-component",
        )

        guidance = await update_action_progress(
            session_id,
            guidance.current_action.action_id,
            GuidanceActionUpdate(progress_state="completed"),
            self.user,
            self.db,
            device_header=str(self.device_id),
            idempotency_header="phase9_boundary_physical_done",
        )
        self.assertEqual(guidance.status, "unsupported_boundary")
        self.assertFalse(guidance.procedure_complete)
        self.assertIsNotNone(guidance.current_action)
        assert guidance.current_action is not None
        boundary = guidance.current_action
        self.assertEqual(boundary.action_key, COMPUTER_SERVICE_BOUNDARY_ACTION_KEY)
        self.assertEqual(boundary.boundary_code, COMPUTER_SERVICE_BOUNDARY_CODE)
        self.assertFalse(boundary.completion_allowed)
        self.assertFalse(boundary.skippable)
        self.assertEqual(boundary.instruction, COMPUTER_SERVICE_BOUNDARY_MESSAGE)
        self.assertEqual(guidance.summary.completed, 1)
        self.assertEqual(guidance.summary.pending, 1)

        completion = await _completion_view(
            self.db,
            user_id=self.user.id,
            session_id=session_id,
        )
        self.assertTrue(completion.supported_partgraph_work_complete)
        self.assertFalse(completion.fully_mechanically_complete)
        self.assertEqual(
            completion.completion_status,
            "unsupported_or_professional_pending",
        )
        self.assertEqual(
            completion.unsupported_action_titles,
            ["Required computer-dependent service"],
        )

        for index, progress_state in enumerate(
            ("completed", "skipped", "blocked"),
            start=1,
        ):
            with self.assertRaises(PartGraphError) as captured:
                await update_action_progress(
                    session_id,
                    boundary.action_id,
                    GuidanceActionUpdate(progress_state=progress_state),
                    self.user,
                    self.db,
                    device_header=str(self.device_id),
                    idempotency_header=f"phase9_boundary_reject_{index}",
                )
            self.assertEqual(
                captured.exception.code,
                "REPAIR_PROCEDURE_ACTION_UNSUPPORTED_BOUNDARY",
            )
            self.assertEqual(
                captured.exception.details["boundary_code"],
                COMPUTER_SERVICE_BOUNDARY_CODE,
            )

        persisted_boundary_state = await self.db.scalar(
            select(RepairProcedureActionState).where(
                RepairProcedureActionState.user_id == self.user.id,
                RepairProcedureActionState.session_id == session_id,
                RepairProcedureActionState.action_id == boundary.action_id,
            )
        )
        self.assertIsNone(persisted_boundary_state)

        progress_events = await self.db.scalar(
            select(func.count())
            .select_from(RepairSessionEvent)
            .where(
                RepairSessionEvent.user_id == self.user.id,
                RepairSessionEvent.session_id == session_id,
                RepairSessionEvent.event_type == "procedure_action_state_changed",
            )
        )
        self.assertEqual(progress_events, 1)

        final_guidance = await _guidance_view(
            self.db,
            user_id=self.user.id,
            session_id=session_id,
            include_plan=False,
        )
        self.assertEqual(final_guidance.status, "unsupported_boundary")
        self.assertFalse(final_guidance.procedure_complete)
        self.assertIsNotNone(final_guidance.current_action)
        assert final_guidance.current_action is not None
        self.assertEqual(
            final_guidance.current_action.action_key,
            COMPUTER_SERVICE_BOUNDARY_ACTION_KEY,
        )


if __name__ == "__main__":
    unittest.main()
