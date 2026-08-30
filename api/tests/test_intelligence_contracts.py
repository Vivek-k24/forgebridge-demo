import asyncio

import pytest

from partgraph.intelligence.contracts import (
    DisabledModelGateway,
    IntelligenceResultKind,
    ModelGatewayUnavailable,
    ModelRequest,
)


def test_disabled_model_gateway_fails_closed() -> None:
    request = ModelRequest(
        purpose="explain_verified_state",
        reason_code="deterministic_path_sufficient",
        result_kind=IntelligenceResultKind.EXPLANATION,
        prompt_template_key="assistance.explain",
        prompt_version="v1",
        prompt_sha256="a" * 64,
        input_payload={"verified_only": True},
    )

    with pytest.raises(ModelGatewayUnavailable, match="MODEL_GATEWAY_DISABLED"):
        asyncio.run(DisabledModelGateway().invoke(request))


def test_intelligence_result_kinds_are_candidate_only_surfaces() -> None:
    assert {item.value for item in IntelligenceResultKind} == {
        "explanation",
        "proposal",
        "classification",
        "ranking",
        "extraction",
    }
