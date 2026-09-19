from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ..errors import ErrorEnvelope
from ..identity.auth.dependencies import AuthSessionDep, CurrentUserDep, require_csrf
from .schemas import EquipmentCatalogItemRead, EquipmentCatalogPage, EquipmentCategoryRead, EquipmentInventoryUpdate
from .service import list_catalog, list_categories, set_inventory_state

router = APIRouter(
    prefix="/api/v1/equipment",
    tags=["Equipment"],
    responses={
        401: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope},
        422: {"model": ErrorEnvelope},
        503: {"model": ErrorEnvelope},
    },
)
CsrfDep = Depends(require_csrf)


@router.get("/categories", response_model=list[EquipmentCategoryRead])
async def categories(user: CurrentUserDep, session: AuthSessionDep) -> list[EquipmentCategoryRead]:
    return await list_categories(session, user_id=user.id)


@router.get("/catalog", response_model=EquipmentCatalogPage)
async def catalog(
    user: CurrentUserDep,
    session: AuthSessionDep,
    category: Annotated[str, Query(min_length=1, max_length=64)],
    q: Annotated[str, Query(max_length=120)] = "",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> EquipmentCatalogPage:
    return await list_catalog(
        session,
        user_id=user.id,
        category=category,
        query=q,
        offset=offset,
        limit=limit,
    )


@router.put(
    "/inventory/{catalog_item_id}",
    response_model=EquipmentCatalogItemRead,
    dependencies=[CsrfDep],
)
async def update_inventory(
    catalog_item_id: UUID,
    payload: EquipmentInventoryUpdate,
    user: CurrentUserDep,
    session: AuthSessionDep,
) -> EquipmentCatalogItemRead:
    return await set_inventory_state(
        session,
        user_id=user.id,
        catalog_item_id=catalog_item_id,
        in_inventory=payload.in_inventory,
        quantity=payload.quantity,
    )
