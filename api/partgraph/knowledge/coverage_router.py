from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status

from ..errors import ErrorEnvelope
from ..identity.auth.dependencies import AuthSessionDep
from ..identity.auth.roles import ReviewerUserDep
from .coverage_schemas import CatalogCoverageBatchRead
from .coverage_service import get_coverage_batch, list_coverage_batches

router = APIRouter(
    prefix="/api/v1/catalog-coverage",
    tags=["Catalog Coverage"],
    responses={401: {"model": ErrorEnvelope}, 403: {"model": ErrorEnvelope}},
)
BatchKey = Annotated[
    str,
    Path(min_length=1, max_length=96, pattern=r"^[a-z0-9][a-z0-9._-]*$"),
]


@router.get("/batches", response_model=list[CatalogCoverageBatchRead])
async def coverage_batches(
    user: ReviewerUserDep,
    session: AuthSessionDep,
) -> list[CatalogCoverageBatchRead]:
    del user
    return await list_coverage_batches(session)


@router.get("/batches/{batch_key}", response_model=CatalogCoverageBatchRead)
async def coverage_batch(
    batch_key: BatchKey,
    user: ReviewerUserDep,
    session: AuthSessionDep,
) -> CatalogCoverageBatchRead:
    del user
    item = await get_coverage_batch(session, batch_key)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="catalog coverage batch not found",
        )
    return item
