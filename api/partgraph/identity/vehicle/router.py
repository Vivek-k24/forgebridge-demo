from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from .policy import validate_supported_year
from .schemas import (
    VehicleBrandRead,
    VehicleConfigurationRead,
    VehicleSelectionInput,
    VehicleSelectionNormalized,
    VehicleSelectionResult,
    VehicleSpecificationProfileRead,
)
from .service import (
    get_configuration,
    get_specification_profile,
    list_configurations,
    list_generation_options,
    list_model_options,
    list_trim_options,
    resolve_selection,
)
from .taxonomy import VehicleIdentityError, supported_brand_records

router = APIRouter(prefix="/api/v1", tags=["Vehicle Identity"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _vehicle_error(exc: VehicleIdentityError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=str(exc),
    )


def _validated_year(year: int) -> int:
    try:
        return validate_supported_year(year)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.get("/vehicle-brands", response_model=list[VehicleBrandRead])
async def vehicle_brands() -> list[VehicleBrandRead]:
    return [VehicleBrandRead.model_validate(item) for item in supported_brand_records()]


@router.get("/vehicle-options/models", response_model=list[str])
async def vehicle_models(
    session: SessionDep,
    year: int,
    market: Annotated[str, Query(min_length=1, max_length=64)],
    make: Annotated[str, Query(min_length=1, max_length=64)],
    q: Annotated[str | None, Query(max_length=96)] = None,
) -> list[str]:
    try:
        return await list_model_options(
            session,
            year=_validated_year(year),
            market=market,
            make=make,
            query=q,
        )
    except VehicleIdentityError as exc:
        raise _vehicle_error(exc) from exc


@router.get("/vehicle-options/trims", response_model=list[str])
async def vehicle_trims(
    session: SessionDep,
    year: int,
    market: Annotated[str, Query(min_length=1, max_length=64)],
    make: Annotated[str, Query(min_length=1, max_length=64)],
    model: Annotated[str, Query(min_length=1, max_length=96)],
    q: Annotated[str | None, Query(max_length=128)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[str]:
    try:
        return await list_trim_options(
            session,
            year=_validated_year(year),
            market=market,
            make=make,
            model=model,
            query=q,
            limit=limit,
        )
    except VehicleIdentityError as exc:
        raise _vehicle_error(exc) from exc


@router.get("/vehicle-options/generations", response_model=list[str])
async def vehicle_generations(
    session: SessionDep,
    year: int,
    market: Annotated[str, Query(min_length=1, max_length=64)],
    make: Annotated[str, Query(min_length=1, max_length=64)],
    model: Annotated[str, Query(min_length=1, max_length=96)],
    trim: Annotated[str | None, Query(max_length=128)] = None,
    q: Annotated[str | None, Query(max_length=96)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[str]:
    try:
        return await list_generation_options(
            session,
            year=_validated_year(year),
            market=market,
            make=make,
            model=model,
            trim=trim,
            query=q,
            limit=limit,
        )
    except VehicleIdentityError as exc:
        raise _vehicle_error(exc) from exc


@router.post("/vehicle-selection/resolve", response_model=VehicleSelectionResult)
async def selection_resolution(
    payload: VehicleSelectionInput,
    session: SessionDep,
) -> VehicleSelectionResult:
    try:
        resolution, normalized, matches = await resolve_selection(session, payload)
    except VehicleIdentityError as exc:
        raise _vehicle_error(exc) from exc

    return VehicleSelectionResult(
        resolution=resolution,
        normalized=VehicleSelectionNormalized.model_validate(normalized),
        matches=[VehicleConfigurationRead.model_validate(item) for item in matches],
    )


@router.get(
    "/vehicle-configurations",
    response_model=list[VehicleConfigurationRead],
)
async def configurations(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[VehicleConfigurationRead]:
    items = await list_configurations(session, limit)
    return [VehicleConfigurationRead.model_validate(item) for item in items]


@router.get(
    "/vehicle-configurations/{configuration_id}/profile",
    response_model=VehicleSpecificationProfileRead,
)
async def configuration_profile(
    configuration_id: UUID,
    session: SessionDep,
) -> VehicleSpecificationProfileRead:
    item = await get_specification_profile(session, configuration_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="vehicle specification profile not found",
        )
    return VehicleSpecificationProfileRead.model_validate(item)


@router.get(
    "/vehicle-configurations/{configuration_id}",
    response_model=VehicleConfigurationRead,
)
async def configuration(
    configuration_id: UUID,
    session: SessionDep,
) -> VehicleConfigurationRead:
    item = await get_configuration(session, configuration_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="vehicle configuration not found",
        )
    return VehicleConfigurationRead.model_validate(item)
