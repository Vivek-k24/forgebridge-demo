from partgraph.catalog.models import CatalogVerifiedEvidence as LegacyCatalogVerifiedEvidence
from partgraph.catalog.source_models import MechanicalClaim as LegacyMechanicalClaim
from partgraph.knowledge import models as knowledge_models
from partgraph.repair_definition.models import RepairDefinition as LegacyRepairDefinition
from partgraph.repair_definition.models import (
    RepairRequirementState,
    UserGarageInventoryItem,
)


def test_legacy_paths_reexport_the_same_canonical_orm_classes() -> None:
    assert LegacyCatalogVerifiedEvidence is knowledge_models.CatalogVerifiedEvidence
    assert LegacyMechanicalClaim is knowledge_models.MechanicalClaim
    assert LegacyRepairDefinition is knowledge_models.RepairDefinition

    assert knowledge_models.CatalogVerifiedEvidence.__module__ == "partgraph.knowledge.models"
    assert knowledge_models.MechanicalClaim.__module__ == "partgraph.knowledge.models"
    assert knowledge_models.RepairDefinition.__module__ == "partgraph.knowledge.models"


def test_private_readiness_state_is_not_owned_by_knowledge() -> None:
    assert not hasattr(knowledge_models, "UserGarageInventoryItem")
    assert not hasattr(knowledge_models, "RepairRequirementState")
    assert UserGarageInventoryItem.__module__ == "partgraph.repair_definition.models"
    assert RepairRequirementState.__module__ == "partgraph.repair_definition.models"


def test_compatibility_paths_do_not_duplicate_sqlalchemy_tables() -> None:
    assert (
        LegacyCatalogVerifiedEvidence.__table__
        is knowledge_models.CatalogVerifiedEvidence.__table__
    )
    assert LegacyMechanicalClaim.__table__ is knowledge_models.MechanicalClaim.__table__
    assert LegacyRepairDefinition.__table__ is knowledge_models.RepairDefinition.__table__
