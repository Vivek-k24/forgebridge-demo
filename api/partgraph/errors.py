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
