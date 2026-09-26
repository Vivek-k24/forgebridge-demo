from __future__ import annotations

from uuid import UUID

from fastapi import status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import ErrorCode, PartGraphError
from .catalog_meta import CATEGORY_META
from .models import EquipmentCatalogItem, OwnerEquipmentItem
from .schemas import EquipmentCatalogItemRead, EquipmentCatalogPage, EquipmentCategoryRead


def _search_without_whitespace(value: str) -> str:
    return "".join(value.lower().split())


async def list_categories(session: AsyncSession, *, user_id: UUID) -> list[EquipmentCategoryRead]:
    catalog_counts = dict(
        (await session.execute(
            select(EquipmentCatalogItem.category, func.count(EquipmentCatalogItem.id))
            .where(EquipmentCatalogItem.is_active.is_(True))
            .group_by(EquipmentCatalogItem.category)
        )).all()
    )
    inventory_counts = dict(
        (await session.execute(
            select(EquipmentCatalogItem.category, func.count(OwnerEquipmentItem.id))
            .join(OwnerEquipmentItem, OwnerEquipmentItem.catalog_item_id == EquipmentCatalogItem.id)
            .where(OwnerEquipmentItem.user_id == user_id, EquipmentCatalogItem.is_active.is_(True))
            .group_by(EquipmentCatalogItem.category)
        )).all()
    )
    return [
        EquipmentCategoryRead(
            key=key,
            label=label,
            visual_key=visual_key,
            total_count=int(catalog_counts.get(key, 0)),
            inventory_count=int(inventory_counts.get(key, 0)),
        )
        for key, (label, visual_key) in CATEGORY_META.items()
    ]


async def list_catalog(
    session: AsyncSession,
    *,
    user_id: UUID,
    category: str,
    query: str,
    offset: int,
    limit: int,
) -> EquipmentCatalogPage:
    if category not in CATEGORY_META:
        raise PartGraphError(
            code=ErrorCode.REQUEST_VALIDATION_FAILED,
            message="Choose a valid inventory category before searching.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    normalized_query = " ".join(query.strip().split())[:120]
    filters = [
        EquipmentCatalogItem.category == category,
        EquipmentCatalogItem.is_active.is_(True),
    ]
    if normalized_query:
        pattern = f"%{normalized_query}%"
        compact_pattern = f"%{_search_without_whitespace(normalized_query)}%"
        filters.append(
            or_(
                EquipmentCatalogItem.name.ilike(pattern),
                EquipmentCatalogItem.keywords.ilike(pattern),
                func.regexp_replace(
                    func.lower(EquipmentCatalogItem.name),
                    "[[:space:]]+",
                    "",
                    "g",
                ).like(compact_pattern),
                func.regexp_replace(
                    func.lower(EquipmentCatalogItem.keywords),
                    "[[:space:]]+",
                    "",
                    "g",
                ).like(compact_pattern),
            )
        )

    total = int(await session.scalar(select(func.count(EquipmentCatalogItem.id)).where(*filters)) or 0)
    rows = (
        await session.execute(
            select(EquipmentCatalogItem, OwnerEquipmentItem.quantity)
            .outerjoin(
                OwnerEquipmentItem,
                (OwnerEquipmentItem.catalog_item_id == EquipmentCatalogItem.id)
                & (OwnerEquipmentItem.user_id == user_id),
            )
            .where(*filters)
            .order_by(EquipmentCatalogItem.name.asc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    items = [
        EquipmentCatalogItemRead(
            id=item.id,
            catalog_key=item.catalog_key,
            category=item.category,
            name=item.name,
            visual_key=item.visual_key,
            in_inventory=quantity is not None,
            quantity=quantity,
        )
        for item, quantity in rows
    ]
    return EquipmentCatalogPage(
        category=category,
        query=normalized_query,
        total=total,
        offset=offset,
        limit=limit,
        items=items,
    )


async def set_inventory_state(
    session: AsyncSession,
    *,
    user_id: UUID,
    catalog_item_id: UUID,
    in_inventory: bool,
    quantity: int,
) -> EquipmentCatalogItemRead:
    item = await session.scalar(
        select(EquipmentCatalogItem).where(
            EquipmentCatalogItem.id == catalog_item_id,
            EquipmentCatalogItem.is_active.is_(True),
        )
    )
    if item is None:
        raise PartGraphError(
            code=ErrorCode.REQUEST_NOT_FOUND,
            message="Inventory item not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if in_inventory:
        statement = (
            insert(OwnerEquipmentItem)
            .values(user_id=user_id, catalog_item_id=catalog_item_id, quantity=quantity)
            .on_conflict_do_update(
                constraint="uq_owner_equipment_owner_catalog",
                set_={"quantity": quantity, "updated_at": func.now()},
            )
        )
        await session.execute(statement)
        saved_quantity: int | None = quantity
    else:
        await session.execute(
            delete(OwnerEquipmentItem).where(
                OwnerEquipmentItem.user_id == user_id,
                OwnerEquipmentItem.catalog_item_id == catalog_item_id,
            )
        )
        saved_quantity = None

    await session.flush()
    return EquipmentCatalogItemRead(
        id=item.id,
        catalog_key=item.catalog_key,
        category=item.category,
        name=item.name,
        visual_key=item.visual_key,
        in_inventory=in_inventory,
        quantity=saved_quantity,
    )
