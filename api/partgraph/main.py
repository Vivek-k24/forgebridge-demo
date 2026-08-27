import logging
import re
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from .auth.router import router as auth_router
from .config import settings
from .database import database_readiness, engine
from .errors import ErrorCode, PartGraphError, error_response
from .vehicle.router import router as vehicle_router

logger = logging.getLogger("partgraph.api")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
AUTH_BODY_LIMIT_BYTES = 16 * 1024
API_VERSION = "v1"


class LiveHealth(BaseModel):
    service: str
    status: str


class ReadyHealth(LiveHealth):
    database: str
    database_ms: float


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="PartGraph API",
    version="0.3.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "X-PartGraph-CSRF", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-PartGraph-API-Version", "Retry-After"],
)
app.include_router(auth_router)
app.include_router(vehicle_router)


@app.middleware("http")
async def platform_boundary(request: Request, call_next) -> Response:
    supplied_request_id = request.headers.get("x-request-id", "")
    request.state.request_id = (
        supplied_request_id if REQUEST_ID_PATTERN.fullmatch(supplied_request_id) else uuid4().hex
    )

    if request.url.path.startswith("/api/v1/auth/") and request.method in {"POST", "PATCH", "PUT"}:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > AUTH_BODY_LIMIT_BYTES:
                    response = error_response(
                        request,
                        PartGraphError(
                            code=ErrorCode.REQUEST_PAYLOAD_TOO_LARGE,
                            message="Authentication request payload is too large.",
                            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        ),
                    )
                    return _finish_response(request, response, 0.0)
            except ValueError:
                response = error_response(
                    request,
                    PartGraphError(
                        code=ErrorCode.REQUEST_VALIDATION_FAILED,
                        message="Invalid Content-Length header.",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    ),
                )
                return _finish_response(request, response, 0.0)

        body = await request.body()
        if len(body) > AUTH_BODY_LIMIT_BYTES:
            response = error_response(
                request,
                PartGraphError(
                    code=ErrorCode.REQUEST_PAYLOAD_TOO_LARGE,
                    message="Authentication request payload is too large.",
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                ),
            )
            return _finish_response(request, response, 0.0)

    started = perf_counter()
    response = await call_next(request)
    duration_ms = (perf_counter() - started) * 1000
    return _finish_response(request, response, duration_ms)


def _finish_response(request: Request, response: Response, duration_ms: float) -> Response:
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-PartGraph-API-Version"] = API_VERSION
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=(self), geolocation=()"

    if request.url.path.startswith(("/api/v1/auth", "/api/v1/account")):
        response.headers["Cache-Control"] = "no-store"
    elif "Cache-Control" not in response.headers:
        response.headers["Cache-Control"] = "no-cache"

    if settings.cookie_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    if duration_ms >= 10_000:
        logger.warning(
            "code=PERF_HARD_BOUNDARY_EXCEEDED request_id=%s method=%s "
            "path=%s status=%s duration_ms=%.2f",
            request.state.request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
    elif duration_ms >= 3_000:
        logger.warning(
            "code=PERF_SLOW_REQUEST request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            request.state.request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
    return response


@app.exception_handler(PartGraphError)
async def partgraph_error_handler(request: Request, exc: PartGraphError) -> Response:
    return error_response(request, exc)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> Response:
    details = [
        {
            "location": list(error["loc"]),
            "type": error["type"],
            "message": error["msg"],
        }
        for error in exc.errors()
    ]
    return error_response(
        request,
        PartGraphError(
            code=ErrorCode.REQUEST_VALIDATION_FAILED,
            message="Request validation failed.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details=details,
        ),
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException) -> Response:
    code_by_status = {
        status.HTTP_403_FORBIDDEN: ErrorCode.REQUEST_FORBIDDEN,
        status.HTTP_404_NOT_FOUND: ErrorCode.REQUEST_NOT_FOUND,
        status.HTTP_405_METHOD_NOT_ALLOWED: ErrorCode.REQUEST_METHOD_NOT_ALLOWED,
        status.HTTP_409_CONFLICT: ErrorCode.REQUEST_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT: ErrorCode.REQUEST_VALIDATION_FAILED,
        status.HTTP_429_TOO_MANY_REQUESTS: ErrorCode.RATE_LIMITED,
    }
    code = code_by_status.get(exc.status_code, f"HTTP_{exc.status_code}")
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return error_response(
        request,
        PartGraphError(
            code=code,
            message=message,
            status_code=exc.status_code,
            retryable=exc.status_code in {429, 502, 503, 504},
            headers=dict(exc.headers or {}),
        ),
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> Response:
    logger.exception(
        "code=INTERNAL_UNEXPECTED_ERROR request_id=%s method=%s path=%s",
        getattr(request.state, "request_id", "unknown"),
        request.method,
        request.url.path,
    )
    return error_response(
        request,
        PartGraphError(
            code=ErrorCode.INTERNAL_UNEXPECTED_ERROR,
            message="Unexpected server error.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            retryable=True,
        ),
    )


@app.get("/api/v1/health/live", response_model=LiveHealth)
async def live() -> LiveHealth:
    return LiveHealth(service="partgraph-api", status="ok")


@app.get("/api/v1/health/ready", response_model=ReadyHealth)
async def ready() -> ReadyHealth:
    try:
        database_ms = await database_readiness()
    except Exception as exc:
        raise PartGraphError(
            code=ErrorCode.DATABASE_UNAVAILABLE,
            message="Database unavailable.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            retryable=True,
        ) from exc

    return ReadyHealth(
        service="partgraph-api",
        status="ready",
        database="ready",
        database_ms=database_ms,
    )
