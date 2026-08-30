from partgraph.repair_definition.models import (
    RepairRequirementState as LegacyRequirementState,
)
from partgraph.repair_definition.models import (
    UserGarageInventoryItem as LegacyGarageItem,
)
from partgraph.repair_experience import memory_models, readiness_models
from partgraph.repair_experience import models as experience_models
from partgraph.repair_experience import service as experience_service
from partgraph.repair_experience.memory import service as experience_memory_service
from partgraph.repair_memory.models import RepairObservation as LegacyObservation
from partgraph.repair_memory.service import create_observation as legacy_create_observation
from partgraph.repair_session.models import RepairSession as LegacyRepairSession
from partgraph.repair_session.service import append_domain_event as legacy_append_domain_event


def test_legacy_paths_reexport_repair_experience_orm_classes() -> None:
    assert LegacyRepairSession is experience_models.RepairSession
    assert LegacyRequirementState is readiness_models.RepairRequirementState
    assert LegacyGarageItem is readiness_models.UserGarageInventoryItem
    assert LegacyObservation is memory_models.RepairObservation

    assert LegacyRepairSession.__table__ is experience_models.RepairSession.__table__
    assert LegacyRequirementState.__table__ is readiness_models.RepairRequirementState.__table__
    assert LegacyObservation.__table__ is memory_models.RepairObservation.__table__


def test_repair_experience_owns_stateful_orm_models() -> None:
    assert experience_models.RepairSession.__module__ == "partgraph.repair_experience.models"
    assert readiness_models.RepairRequirementState.__module__ == (
        "partgraph.repair_experience.readiness_models"
    )
    assert memory_models.RepairObservation.__module__ == "partgraph.repair_experience.memory_models"


def test_legacy_services_resolve_to_repair_experience_implementations() -> None:
    assert legacy_append_domain_event is experience_service.append_domain_event
    assert legacy_create_observation is experience_memory_service.create_observation
