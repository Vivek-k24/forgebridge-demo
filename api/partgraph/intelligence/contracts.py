from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class IntelligenceResultKind(StrEnum):
    """Non-authoritative result classes an intelligence provider may return."""

    EXPLANATION = "explanation"
    PROPOSAL = "proposal"
    CLASSIFICATION = "classification"
    RANKING = "ranking"
    EXTRACTION = "extraction"


@dataclass(frozen=True, slots=True)
class ModelRequest:
    """Provider-neutral request envelope.

    Payloads contain only the minimum approved context for the requested
    intelligence purpose. Canonical writes and RepairSession mutations are not
    capabilities of this contract.
    """

    purpose: str
    reason_code: str
    result_kind: IntelligenceResultKind
    prompt_template_key: str
    prompt_version: str
    prompt_sha256: str
    input_payload: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModelResult:
    """Provider-neutral model result suitable for auditing and validation."""

    provider: str
    model: str
    result_kind: IntelligenceResultKind
    output_payload: dict[str, object]
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_microusd: int | None = None
    latency_ms: int | None = None
    confidence: float | None = None


class ModelGateway(Protocol):
    """Boundary implemented by future hosted or local model adapters."""

    async def invoke(self, request: ModelRequest) -> ModelResult: ...


class ModelGatewayUnavailable(RuntimeError):
    """Raised when optional model assistance is intentionally unavailable."""


class DisabledModelGateway:
    """Default gateway for the deterministic-only current product state."""

    async def invoke(self, request: ModelRequest) -> ModelResult:
        del request
        raise ModelGatewayUnavailable("MODEL_GATEWAY_DISABLED")
