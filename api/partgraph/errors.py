from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from fastapi import Request
from pydantic import BaseModel
from starlette.responses import JSONResponse


class ErrorCode(StrEnum):
    REQUEST_VALIDATION_FAILED = "REQUEST_VALIDATION_FAILED"
    REQUEST_PAYLOAD_TOO_LARGE = "REQUEST_PAYLOAD_TOO_LARGE"
    REQUEST_NOT_FOUND = "REQUEST_NOT_FOUND"
    REQUEST_METHOD_NOT_ALLOWED = "REQUEST_METHOD_NOT_ALLOWED"
    REQUEST_CONFLICT = "REQUEST_CONFLICT"
    REQUEST_FORBIDDEN = "REQUEST_FORBIDDEN"
    RATE_LIMITED = "RATE_LIMITED"
    REQUEST_DEADLINE_EXCEEDED = "REQUEST_DEADLINE_EXCEEDED"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
    INTERNAL_UNEXPECTED_ERROR = "INTERNAL_UNEXPECTED_ERROR"

    AUTH_CSRF_FAILED = "AUTH_CSRF_FAILED"
    AUTH_ORIGIN_REJECTED = "AUTH_ORIGIN_REJECTED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_SESSION_EXPIRED = "AUTH_SESSION_EXPIRED"
    AUTH_SESSION_REVOKED = "AUTH_SESSION_REVOKED"
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_IDENTITY_CONFLICT = "AUTH_IDENTITY_CONFLICT"
    AUTH_RATE_LIMITED = "AUTH_RATE_LIMITED"
    AUTH_ADMIN_REQUIRED = "AUTH_ADMIN_REQUIRED"
    RBAC_ROLE_REQUIRED = "RBAC_ROLE_REQUIRED"

    VEHICLE_MODEL_PROVIDER_TIMEOUT = "VEHICLE_MODEL_PROVIDER_TIMEOUT"
    VEHICLE_MODEL_PROVIDER_UNAVAILABLE = "VEHICLE_MODEL_PROVIDER_UNAVAILABLE"
    VEHICLE_MODEL_PROVIDER_INVALID_RESPONSE = "VEHICLE_MODEL_PROVIDER_INVALID_RESPONSE"

    VIN_INVALID_FORMAT = "VIN_INVALID_FORMAT"
    VIN_CHECK_DIGIT_INVALID = "VIN_CHECK_DIGIT_INVALID"
    VIN_CRYPTO_UNAVAILABLE = "VIN_CRYPTO_UNAVAILABLE"
    VIN_PROVIDER_TIMEOUT = "VIN_PROVIDER_TIMEOUT"
    VIN_PROVIDER_UNAVAILABLE = "VIN_PROVIDER_UNAVAILABLE"
    VIN_PROVIDER_INVALID_RESPONSE = "VIN_PROVIDER_INVALID_RESPONSE"
    VIN_DECODE_FAILED = "VIN_DECODE_FAILED"
    VIN_DECODE_REQUIRED = "VIN_DECODE_REQUIRED"
    VIN_UNSUPPORTED_VEHICLE = "VIN_UNSUPPORTED_VEHICLE"

    USER_VEHICLE_NOT_FOUND = "USER_VEHICLE_NOT_FOUND"
    USER_VEHICLE_VIN_EXISTS = "USER_VEHICLE_VIN_EXISTS"
    USER_VEHICLE_ARCHIVED = "USER_VEHICLE_ARCHIVED"

    REPAIR_SESSION_NOT_FOUND = "REPAIR_SESSION_NOT_FOUND"
    REPAIR_SESSION_ARCHIVED = "REPAIR_SESSION_ARCHIVED"
    REPAIR_SESSION_DEVICE_ID_INVALID = "REPAIR_SESSION_DEVICE_ID_INVALID"
    REPAIR_SESSION_IDEMPOTENCY_INVALID = "REPAIR_SESSION_IDEMPOTENCY_INVALID"
    REPAIR_SESSION_IDEMPOTENCY_CONFLICT = "REPAIR_SESSION_IDEMPOTENCY_CONFLICT"
    REPAIR_SESSION_LEASE_REQUIRED = "REPAIR_SESSION_LEASE_REQUIRED"
    REPAIR_SESSION_LEASE_HELD = "REPAIR_SESSION_LEASE_HELD"
    REPAIR_SESSION_STATE_CONFLICT = "REPAIR_SESSION_STATE_CONFLICT"
    REPAIR_SESSION_STATE_CORRUPT = "REPAIR_SESSION_STATE_CORRUPT"

    OFFLINE_REPAIR_PACK_UNAVAILABLE = "OFFLINE_REPAIR_PACK_UNAVAILABLE"

    CURATION_RECORD_NOT_FOUND = "CURATION_RECORD_NOT_FOUND"
    CURATION_REVIEW_CONFLICT = "CURATION_REVIEW_CONFLICT"

    KNOWLEDGE_SOURCE_NOT_FOUND = "KNOWLEDGE_SOURCE_NOT_FOUND"
    KNOWLEDGE_SOURCE_PROHIBITED = "KNOWLEDGE_SOURCE_PROHIBITED"
    KNOWLEDGE_SOURCE_NOT_APPROVED = "KNOWLEDGE_SOURCE_NOT_APPROVED"
    KNOWLEDGE_CANDIDATE_INVALID = "KNOWLEDGE_CANDIDATE_INVALID"
    KNOWLEDGE_EVIDENCE_NOT_FOUND = "KNOWLEDGE_EVIDENCE_NOT_FOUND"
    KNOWLEDGE_PUBLICATION_CONFLICT = "KNOWLEDGE_PUBLICATION_CONFLICT"
    KNOWLEDGE_CONFLICT_NOT_FOUND = "KNOWLEDGE_CONFLICT_NOT_FOUND"
    KNOWLEDGE_CONFLICT_RESOLUTION_INVALID = "KNOWLEDGE_CONFLICT_RESOLUTION_INVALID"

    OPERATOR_USER_NOT_FOUND = "OPERATOR_USER_NOT_FOUND"
    OPERATOR_LAST_ADMIN_REQUIRED = "OPERATOR_LAST_ADMIN_REQUIRED"

    STORAGE_LOCATION_NOT_FOUND = "STORAGE_LOCATION_NOT_FOUND"
    FASTENER_NOT_FOUND = "FASTENER_NOT_FOUND"
    INVENTORY_ITEM_NOT_FOUND = "INVENTORY_ITEM_NOT_FOUND"
    OBSERVATION_NOT_FOUND = "OBSERVATION_NOT_FOUND"
    PHOTO_EVIDENCE_NOT_FOUND = "PHOTO_EVIDENCE_NOT_FOUND"
    PHOTO_ATTACHMENT_INVALID = "PHOTO_ATTACHMENT_INVALID"
    PHOTO_TOO_LARGE = "PHOTO_TOO_LARGE"
    PHOTO_MEDIA_TYPE_UNSUPPORTED = "PHOTO_MEDIA_TYPE_UNSUPPORTED"
    PHOTO_STORAGE_CORRUPT = "PHOTO_STORAGE_CORRUPT"
    PHOTO_CONTENT_UNAVAILABLE = "PHOTO_CONTENT_UNAVAILABLE"


class ErrorOwner(StrEnum):
    PLATFORM = "partgraph.main"
    AUTH = "partgraph.identity.auth"
    VEHICLE_IDENTITY = "partgraph.identity.vehicle"
    USER_VEHICLE = "partgraph.identity.user_vehicle"
    REPAIR_SESSION = "partgraph.repair_experience"
    REPAIR_BINDING = "partgraph.repair_experience.repair_definition_binding"
    REPAIR_READINESS = "partgraph.repair_experience.readiness"
    REPAIR_GUIDANCE = "partgraph.repair_experience.guidance"
    REPAIR_COMPLETION = "partgraph.repair_experience.completion"
    REPAIR_RECOVERY = "partgraph.repair_experience.recovery"
    REPAIR_MEMORY = "partgraph.repair_experience.memory"
    OFFLINE = "partgraph.repair_experience.offline"
    KNOWLEDGE = "partgraph.knowledge"
    EQUIPMENT = "partgraph.equipment"
    OPERATOR = "partgraph.operator"


ERROR_FAMILY_OWNERS: tuple[tuple[str, ErrorOwner], ...] = (
    ("VEHICLE_MODEL_", ErrorOwner.VEHICLE_IDENTITY),
    ("USER_VEHICLE_", ErrorOwner.USER_VEHICLE),
    ("VIN_", ErrorOwner.USER_VEHICLE),
    ("REPAIR_DEFINITION_", ErrorOwner.REPAIR_BINDING),
    ("REPAIR_READINESS_", ErrorOwner.REPAIR_READINESS),
    ("REPAIR_PROCEDURE_", ErrorOwner.REPAIR_GUIDANCE),
    ("REPAIR_GUIDANCE_", ErrorOwner.REPAIR_GUIDANCE),
    ("REPAIR_COMPLETION_", ErrorOwner.REPAIR_COMPLETION),
    ("REPAIR_RECOVERY_", ErrorOwner.REPAIR_RECOVERY),
    ("REPAIR_SESSION_", ErrorOwner.REPAIR_SESSION),
    ("STORAGE_LOCATION_", ErrorOwner.REPAIR_MEMORY),
    ("FASTENER_", ErrorOwner.REPAIR_MEMORY),
    ("INVENTORY_ITEM_", ErrorOwner.REPAIR_MEMORY),
    ("OBSERVATION_", ErrorOwner.REPAIR_MEMORY),
    ("PHOTO_", ErrorOwner.REPAIR_MEMORY),
    ("OFFLINE_", ErrorOwner.OFFLINE),
    ("CURATION_", ErrorOwner.KNOWLEDGE),
    ("KNOWLEDGE_", ErrorOwner.KNOWLEDGE),
    ("EQUIPMENT_", ErrorOwner.EQUIPMENT),
    ("PROVIDER_", ErrorOwner.OPERATOR),
    ("OPERATOR_", ErrorOwner.OPERATOR),
    ("RBAC_", ErrorOwner.AUTH),
    ("AUTH_", ErrorOwner.AUTH),
    ("REQUEST_", ErrorOwner.PLATFORM),
    ("RATE_LIMITED", ErrorOwner.PLATFORM),
    ("DATABASE_", ErrorOwner.PLATFORM),
    ("INTERNAL_", ErrorOwner.PLATFORM),
)


def error_code_owner(code: ErrorCode | str) -> ErrorOwner | None:
    value = str(code)
    for prefix, owner in ERROR_FAMILY_OWNERS:
        if value.startswith(prefix):
            return owner
    return None


UNOWNED_REGISTERED_ERROR_CODES = tuple(
    code for code in ErrorCode if error_code_owner(code) is None
)
if UNOWNED_REGISTERED_ERROR_CODES:
    raise RuntimeError(
        "Registered PartGraph error codes must have a module owner: "
        + ", ".join(str(code) for code in UNOWNED_REGISTERED_ERROR_CODES)
    )


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    retryable: bool = False
    details: Any | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody


@dataclass(slots=True)
class PartGraphError(Exception):
    code: ErrorCode | str
    message: str
    status_code: int
    retryable: bool = False
    details: Any | None = None
    headers: dict[str, str] | None = None

    def __str__(self) -> str:
        return self.message


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def error_response(request: Request, error: PartGraphError) -> JSONResponse:
    payload = ErrorEnvelope(
        error=ErrorBody(
            code=str(error.code),
            message=error.message,
            request_id=request_id(request),
            retryable=error.retryable,
            details=error.details,
        )
    )
    return JSONResponse(
        status_code=error.status_code,
        content=payload.model_dump(mode="json", exclude_none=True),
        headers=error.headers,
    )
