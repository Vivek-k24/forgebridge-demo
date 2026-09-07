from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_session
from ..errors import ErrorCode, PartGraphError
from ..identity.auth.dependencies import CurrentUserDep, require_csrf
from .catalog_scope import US_IDENTITY_MAKES, canonical_scoped_make
from .workbench_schemas import (
    CatalogCollectionJobRead,
    CatalogWorkbenchDashboardRead,
    CatalogWorkbenchLogRead,
    CatalogWorkbenchSourceRead,
)
from .workbench_service import (
    job_logs,
    job_sources,
    pause_make_job,
    resume_make_job,
    start_make_job,
    workbench_dashboard,
)

router = APIRouter(prefix="/api/v1/catalog-workbench", tags=["Catalog Workbench"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
CsrfDep = Annotated[None, Depends(require_csrf)]
BatchKey = Annotated[
    str,
    Path(min_length=1, max_length=96, pattern=r"^[a-z0-9][a-z0-9._-]*$"),
]
MakePath = Annotated[str, Path(min_length=1, max_length=64)]


def _require_spec_collection(make: str) -> None:
    if canonical_scoped_make(make) is None:
        raise PartGraphError(
            code=ErrorCode.REQUEST_FORBIDDEN,
            message=(
                "Catalog collection is currently limited to "
                f"{', '.join(US_IDENTITY_MAKES)}."
            ),
            status_code=status.HTTP_403_FORBIDDEN,
        )
    if not settings.workbench_spec_collection_enabled:
        raise PartGraphError(
            code=ErrorCode.REQUEST_CONFLICT,
            message=(
                "Technical specification collection is paused while the US "
                "1996-2027 make/model/trim inventory is being built."
            ),
            status_code=status.HTTP_409_CONFLICT,
        )


@router.get(
    "/batches/{batch_key}",
    response_model=CatalogWorkbenchDashboardRead,
)
async def dashboard(
    batch_key: BatchKey,
    session: SessionDep,
    _user: CurrentUserDep,
) -> CatalogWorkbenchDashboardRead:
    return await workbench_dashboard(session, batch_key)


@router.post(
    "/batches/{batch_key}/makes/{make}/start",
    response_model=CatalogCollectionJobRead,
)
async def start_make(
    batch_key: BatchKey,
    make: MakePath,
    session: SessionDep,
    _user: CurrentUserDep,
    _csrf: CsrfDep,
) -> CatalogCollectionJobRead:
    _require_spec_collection(make)
    return await start_make_job(session, batch_key, make)


@router.post(
    "/batches/{batch_key}/makes/{make}/pause",
    response_model=CatalogCollectionJobRead,
)
async def pause_make(
    batch_key: BatchKey,
    make: MakePath,
    session: SessionDep,
    _user: CurrentUserDep,
    _csrf: CsrfDep,
) -> CatalogCollectionJobRead:
    return await pause_make_job(session, batch_key, make)


@router.post(
    "/batches/{batch_key}/makes/{make}/resume",
    response_model=CatalogCollectionJobRead,
)
async def resume_make(
    batch_key: BatchKey,
    make: MakePath,
    session: SessionDep,
    _user: CurrentUserDep,
    _csrf: CsrfDep,
) -> CatalogCollectionJobRead:
    _require_spec_collection(make)
    return await resume_make_job(session, batch_key, make)


@router.get(
    "/jobs/{job_id}/logs",
    response_model=list[CatalogWorkbenchLogRead],
)
async def logs(
    job_id: UUID,
    session: SessionDep,
    _user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 150,
) -> list[CatalogWorkbenchLogRead]:
    return await job_logs(session, job_id, limit)


@router.get(
    "/jobs/{job_id}/sources",
    response_model=list[CatalogWorkbenchSourceRead],
)
async def sources(
    job_id: UUID,
    session: SessionDep,
    _user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 150,
) -> list[CatalogWorkbenchSourceRead]:
    return await job_sources(session, job_id, limit)
