from __future__ import annotations

import json
import logging
import os
import re
import secrets
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID

OBSERVABILITY_SCHEMA = "partgraph.observability.v1"
SERVICE_NAME = "partgraph-api"
_TRACEPARENT_PATTERN = re.compile(
    r"^(?P<version>[0-9a-f]{2})-(?P<trace_id>[0-9a-f]{32})-"
    r"(?P<span_id>[0-9a-f]{16})-(?P<trace_flags>[0-9a-f]{2})$"
)
_ZERO_TRACE_ID = "0" * 32
_ZERO_SPAN_ID = "0" * 16
_MUTATION_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

logger = logging.getLogger("partgraph.observability")
_request_id_context: ContextVar[str | None] = ContextVar(
    "partgraph_observability_request_id",
    default=None,
)
_trace_context: ContextVar[TraceContext | None]


@dataclass(frozen=True, slots=True)
class TraceContext:
    trace_id: str
    span_id: str
    trace_flags: str = "01"

    @property
    def traceparent(self) -> str:
        return f"00-{self.trace_id}-{self.span_id}-{self.trace_flags}"


_trace_context = ContextVar("partgraph_observability_trace_context", default=None)


def _new_trace_context() -> TraceContext:
    return TraceContext(
        trace_id=secrets.token_hex(16),
        span_id=secrets.token_hex(8),
    )


def trace_context_from_header(value: str | None) -> TraceContext:
    """Accept valid W3C trace context or create a new PartGraph request context."""

    if value:
        match = _TRACEPARENT_PATTERN.fullmatch(value.strip().casefold())
        if match is not None:
            version = match.group("version")
            trace_id = match.group("trace_id")
            parent_span_id = match.group("span_id")
            if version != "ff" and trace_id != _ZERO_TRACE_ID and parent_span_id != _ZERO_SPAN_ID:
                return TraceContext(
                    trace_id=trace_id,
                    span_id=secrets.token_hex(8),
                    trace_flags=match.group("trace_flags"),
                )
    return _new_trace_context()


def bind_request_context(*, request_id: str, traceparent: str | None) -> TraceContext:
    context = trace_context_from_header(traceparent)
    _request_id_context.set(request_id)
    _trace_context.set(context)
    return context


def current_trace_context() -> TraceContext:
    context = _trace_context.get()
    if context is None:
        context = _new_trace_context()
        _trace_context.set(context)
    return context


def current_request_id() -> str | None:
    return _request_id_context.get()


def is_mutation_method(method: str) -> bool:
    return method.upper() in _MUTATION_METHODS


def _environment_name() -> str:
    return (
        os.getenv("VERCEL_ENV")
        or os.getenv("PARTGRAPH_ENVIRONMENT")
        or "local"
    ).strip()


def _deployment_reference() -> str | None:
    for variable_name in (
        "VERCEL_GIT_COMMIT_SHA",
        "VERCEL_URL",
    ):
        value = os.getenv(variable_name)
        if value and value.strip():
            return value.strip()
    return None


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (UUID, Enum)):
        return str(getattr(value, "value", value))
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return str(value)


def build_event(
    event_name: str,
    *,
    severity: str = "INFO",
    request_id: str | None = None,
    trace_context: TraceContext | None = None,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one low-cardinality, OpenTelemetry-compatible structured log event."""

    context = trace_context or current_trace_context()
    payload: dict[str, Any] = {
        "schema": OBSERVABILITY_SCHEMA,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "service.name": SERVICE_NAME,
        "deployment.environment": _environment_name(),
        "event.name": event_name,
        "severity": severity.upper(),
        "trace_id": context.trace_id,
        "span_id": context.span_id,
    }
    deployment_reference = _deployment_reference()
    if deployment_reference is not None:
        payload["deployment.reference"] = deployment_reference
    effective_request_id = request_id or current_request_id()
    if effective_request_id is not None:
        payload["request.id"] = effective_request_id
    if attributes:
        for key, value in attributes.items():
            payload[key] = _json_value(value)
    return payload


def emit_event(
    event_name: str,
    *,
    level: int = logging.INFO,
    request_id: str | None = None,
    trace_context: TraceContext | None = None,
    **attributes: Any,
) -> dict[str, Any]:
    payload = build_event(
        event_name,
        severity=logging.getLevelName(level),
        request_id=request_id,
        trace_context=trace_context,
        attributes=attributes,
    )
    logger.log(
        level,
        json.dumps(payload, separators=(",", ":"), sort_keys=True),
    )
    return payload
