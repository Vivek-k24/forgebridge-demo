from partgraph import main
from partgraph.assistance import router as assistance_router_module
from partgraph.assistance import service as assistance_service
from partgraph.identity import actors
from partgraph.knowledge import router as knowledge_router_module
from partgraph.repair_experience import guidance, readiness, repair_definition_binding
from partgraph.repair_experience import router as repair_experience_router_module
from partgraph.repair_experience.auth import dependencies as repair_experience_auth
from partgraph.repair_experience.memory import router as repair_memory_router_module


def test_application_composition_root_uses_canonical_domain_routers() -> None:
    assert main.repair_session_router is repair_experience_router_module.router
    assert main.repair_memory_router is repair_memory_router_module.router
    assert main.repair_definition_router is knowledge_router_module.router
    assert main.repair_definition_binding_router is repair_definition_binding.router
    assert main.repair_readiness_router is readiness.router
    assert main.repair_guidance_router is guidance.router


def test_assistance_consumes_canonical_repair_experience() -> None:
    assert assistance_router_module._guidance_view is guidance._guidance_view
    assert assistance_router_module.RepairGuidanceRead is guidance.RepairGuidanceRead
    assert assistance_service.RepairGuidanceRead is guidance.RepairGuidanceRead


def test_repair_experience_private_auth_seam_uses_identity_owner_boundary() -> None:
    assert repair_experience_auth.AuthSessionDep is actors.AuthSessionDep
    assert repair_experience_auth.CurrentUserDep is actors.CurrentUserDep
    assert repair_experience_auth.require_csrf is actors.require_csrf
