import asyncio

from sqlalchemy import select

from partgraph.database import session_factory
from partgraph.identity.vehicle.models import VehicleConfiguration
from partgraph.identity.vehicle.schemas import VehicleSelectionInput
from partgraph.identity.vehicle.service import resolve_selection
from partgraph.knowledge.models import (
    CatalogSource,
    CatalogVerifiedEvidence,
    MechanicalClaim,
    RepairDefinition,
)

IDENTITY_HASH = "31111f85a4f95ba85abbe452c132c20eddd02e0f7242c088e49f1a328bee45cb"
SOURCE_KEY = "nhtsa-honda-tech-line-dp10004"
SOURCE_RECORD_ID = "INRD-DP10004-48962P:p390"
NORMALIZED_KEY = "vehicle:US:2009:Honda:CIVIC:HYBRID"


def test_curated_honda_identity_is_verified_and_has_no_repair_truth() -> None:
    async def scenario() -> None:
        async with session_factory() as session:
            source = await session.scalar(
                select(CatalogSource).where(CatalogSource.source_key == SOURCE_KEY)
            )
            assert source is not None
            assert source.source_class == "government"
            assert source.license_status == "approved"
            assert source.automation_allowed is False

            evidence = await session.scalar(
                select(CatalogVerifiedEvidence).where(
                    CatalogVerifiedEvidence.source_record_id == SOURCE_RECORD_ID
                )
            )
            assert evidence is not None
            assert evidence.candidate_type == "vehicle_identity"
            assert evidence.source_type == "government"
            assert evidence.verified_payload["year"] == 2009
            assert evidence.verified_payload["trim"] == "HYBRID"
            assert evidence.verified_payload["engine"] == "I4 HYBRID"
            assert evidence.verified_payload["transmission"] == "CVT"
            assert evidence.verified_payload["body_style"] is None
            assert evidence.verified_payload["drivetrain"] is None
            assert "engine_displacement" in evidence.provenance["excluded_from_canonical_identity"]

            vehicle = await session.scalar(
                select(VehicleConfiguration).where(
                    VehicleConfiguration.identity_hash == IDENTITY_HASH
                )
            )
            assert vehicle is not None
            assert vehicle.year == 2009
            assert vehicle.market == "US"
            assert vehicle.make == "Honda"
            assert vehicle.model == "CIVIC"
            assert vehicle.trim == "HYBRID"
            assert vehicle.engine == "I4 HYBRID"
            assert vehicle.transmission == "CVT"
            assert vehicle.body_style is None
            assert vehicle.drivetrain is None
            assert vehicle.identity_source == "nhtsa"
            assert vehicle.verification_status == "verified"

            claim = await session.scalar(
                select(MechanicalClaim).where(MechanicalClaim.normalized_key == NORMALIZED_KEY)
            )
            assert claim is not None
            assert claim.vehicle_configuration_id == vehicle.id
            assert claim.verified_evidence_id == evidence.id
            assert claim.claim_domain == "vehicle_identity"
            assert claim.explicit_claim is True
            assert claim.exact_applicability is True
            assert claim.promotion_state == "verified"

            repair_definition = await session.scalar(
                select(RepairDefinition.id).where(
                    RepairDefinition.vehicle_configuration_id == vehicle.id
                )
            )
            assert repair_definition is None

    asyncio.run(scenario())


def test_richer_owner_input_matches_the_less_specific_verified_identity() -> None:
    async def scenario() -> None:
        async with session_factory() as session:
            resolution, normalized, matches = await resolve_selection(
                session,
                VehicleSelectionInput(
                    year=2009,
                    market="US",
                    make="Honda",
                    model="Civic",
                    trim="Hybrid",
                    engine="1.3L I4 Hybrid",
                    transmission="CVT",
                ),
            )

            assert resolution == "matched"
            assert normalized["engine"] == "1.3L I4 HYBRID"
            assert len(matches) == 1
            assert matches[0].identity_hash == IDENTITY_HASH
            assert matches[0].engine == "I4 HYBRID"

    asyncio.run(scenario())
