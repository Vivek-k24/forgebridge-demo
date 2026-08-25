from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from .schemas import (
    VehicleConfigurationInput,
    VehicleConfigurationRead,
    VehicleConfigurationResult,
)
from .service import (
    VehicleIdentityAmbiguousError,
    create_or_get_configuration,
    get_configuration,
    list_configurations,
)

router = APIRouter(prefix="/api/v1/vehicle-configurations", tags=["Vehicle Identity"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=VehicleConfigurationResult)
async def create_configuration(
    payload: VehicleConfigurationInput,
    session: SessionDep,
) -> VehicleConfigurationResult:
    try:
        configuration, resolution = await create_or_get_configuration(session, payload)
    except VehicleIdentityAmbiguousError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return VehicleConfigurationResult(
        created=resolution == "created",
        resolution=resolution,
        configuration=configuration,
    )


@router.get("", response_model=list[VehicleConfigurationRead])
async def configurations(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[VehicleConfigurationRead]:
    items = await list_configurations(session, limit)
    return [VehicleConfigurationRead.model_validate(item) for item in items]


@router.get("/{configuration_id}", response_model=VehicleConfigurationRead)
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
