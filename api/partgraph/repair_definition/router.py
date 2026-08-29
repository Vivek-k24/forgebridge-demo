from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..errors import ErrorEnvelope
from .schemas import RepairDefinitionManifestRead
from .service import verified_requirement_manifest

router = APIRouter(
    prefix="/api/v1/vehicle-configurations",
    tags=["Repair Requirements"],
    responses={
        404: {"model": ErrorEnvelope},
        422: {"model": ErrorEnvelope},
        500: {"model": ErrorEnvelope},
    },
)
SessionDep = Annotated[AsyncSession, Depends(get_session)]
RepairKey = Annotated[
    str,
    Path(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]*$"),
]


@router.get(
    "/{configuration_id}/repairs/{repair_key}/requirements",
    response_model=RepairDefinitionManifestRead,
)
async def repair_requirements(
    configuration_id: UUID,
    repair_key: RepairKey,
    session: SessionDep,
) -> RepairDefinitionManifestRead:
    return await verified_requirement_manifest(
        session,
        vehicle_configuration_id=configuration_id,
        repair_key=repair_key,
    )
