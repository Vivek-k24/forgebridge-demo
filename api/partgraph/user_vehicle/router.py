from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from ..auth.dependencies import AuthSessionDep, CurrentUserDep, require_csrf
from ..errors import ErrorEnvelope
from .schemas import (
    ManualUserVehicleCreate,
    UserVehicleRead,
    VinDecodeRead,
    VinRequest,
    VinUserVehicleCreate,
)
from .service import (
    archive_user_vehicle,
    create_manual_user_vehicle,
    create_vin_user_vehicle,
    decode_user_vin,
    get_user_vehicle,
    list_user_vehicles,
    serialize_user_vehicle,
    serialize_vin_resolution,
)

ERROR_RESPONSES = {
    401: {"model": ErrorEnvelope},
    403: {"model": ErrorEnvelope},
    404: {"model": ErrorEnvelope},
    409: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
    502: {"model": ErrorEnvelope},
    503: {"model": ErrorEnvelope},
    504: {"model": ErrorEnvelope},
}
router = APIRouter(prefix="/api/v1/user-vehicles", tags=["User Vehicles"], responses=ERROR_RESPONSES)
CsrfDep = Depends(require_csrf)


@router.get("", response_model=list[UserVehicleRead])
async def vehicles(
    user: CurrentUserDep,
    session: AuthSessionDep,
    include_archived: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[UserVehicleRead]:
    items = await list_user_vehicles(
        session,
        user_id=user.id,
        include_archived=include_archived,
        limit=limit,
    )
    return [UserVehicleRead.model_validate(serialize_user_vehicle(item)) for item in items]


@router.post(
    "/manual",
    response_model=UserVehicleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[CsrfDep],
)
async def create_manual(
    payload: ManualUserVehicleCreate,
    user: CurrentUserDep,
    session: AuthSessionDep,
) -> UserVehicleRead:
    item = await create_manual_user_vehicle(
        session,
        user_id=user.id,
        payload=payload,
    )
    return UserVehicleRead.model_validate(serialize_user_vehicle(item))


@router.post("/vin/decode", response_model=VinDecodeRead, dependencies=[CsrfDep])
async def decode_vin(
    payload: VinRequest,
    user: CurrentUserDep,
    session: AuthSessionDep,
) -> VinDecodeRead:
    resolved = await decode_user_vin(
        session,
        user_id=user.id,
        market=payload.market,
        vin_value=payload.vin,
    )
    return serialize_vin_resolution(resolved)


@router.post(
    "/vin",
    response_model=UserVehicleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[CsrfDep],
)
async def create_from_vin(
    payload: VinUserVehicleCreate,
    user: CurrentUserDep,
    session: AuthSessionDep,
) -> UserVehicleRead:
    item = await create_vin_user_vehicle(
        session,
        user_id=user.id,
        payload=payload,
    )
    return UserVehicleRead.model_validate(serialize_user_vehicle(item))


@router.get("/{vehicle_id}", response_model=UserVehicleRead)
async def vehicle(
    vehicle_id: UUID,
    user: CurrentUserDep,
    session: AuthSessionDep,
) -> UserVehicleRead:
    item = await get_user_vehicle(session, user_id=user.id, vehicle_id=vehicle_id)
    if item is None:
        from ..errors import ErrorCode, PartGraphError

        raise PartGraphError(
            code=ErrorCode.USER_VEHICLE_NOT_FOUND,
            message="Vehicle not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return UserVehicleRead.model_validate(serialize_user_vehicle(item))


@router.patch("/{vehicle_id}/archive", response_model=UserVehicleRead, dependencies=[CsrfDep])
async def archive_vehicle(
    vehicle_id: UUID,
    user: CurrentUserDep,
    session: AuthSessionDep,
) -> UserVehicleRead:
    item = await archive_user_vehicle(session, user_id=user.id, vehicle_id=vehicle_id)
    return UserVehicleRead.model_validate(serialize_user_vehicle(item))
