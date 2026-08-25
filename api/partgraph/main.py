from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import settings
from .database import database_readiness, engine


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
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


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
