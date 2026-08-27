from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .auth.router import router as auth_router
from .config import settings
from .database import database_readiness, engine
from .vehicle.router import router as vehicle_router


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
    allow_headers=["Content-Type", "X-PartGraph-CSRF"],
)
app.include_router(auth_router)
app.include_router(vehicle_router)


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=(self), geolocation=()"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/v1/auth") else response.headers.get("Cache-Control", "no-cache")
    if settings.cookie_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/api/v1/health/live", response_model=LiveHealth)
async def live() -> LiveHealth:
    return LiveHealth(service="partgraph-api", status="ok")


@app.get("/api/v1/health/ready", response_model=ReadyHealth)
async def ready() -> ReadyHealth:
    try:
        database_ms = await database_readiness()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc

    return ReadyHealth(
        service="partgraph-api",
        status="ready",
        database="ready",
        database_ms=database_ms,
    )
