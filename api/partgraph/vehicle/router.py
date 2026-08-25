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
from .service import create_or_get_configuration, get_configuration, list_configurations

router = APIRouter(prefix="/api/v1/vehicle-configurations", tags=["Vehicle Identity"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=VehicleConfigurationResult)
async def create_configuration(
    payload: VehicleConfigurationInput,
    session: SessionDep,
) -> VehicleConfigurationResult:
    configuration, created = await create_or_get_configuration(session, payload)
    return VehicleConfigurationResult(created=created, configuration=configuration)


@router.get("", response_model=list[VehicleConfigurationRead])
async def configurations(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[VehicleConfigurationRead]:
    return [VehicleConfigurationRead.model_validate(item) for item in await list_configurations(session, limit)]


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
