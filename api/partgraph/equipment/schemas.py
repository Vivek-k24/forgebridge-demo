from uuid import UUID

from pydantic import BaseModel, Field


class EquipmentCategoryRead(BaseModel):
    key: str
    label: str
    visual_key: str
    total_count: int
    inventory_count: int


class EquipmentCatalogItemRead(BaseModel):
    id: UUID
    catalog_key: str
    category: str
    name: str
    visual_key: str
    in_inventory: bool
    quantity: int | None


class EquipmentCatalogPage(BaseModel):
    category: str
    query: str
    total: int
    offset: int
    limit: int
    items: list[EquipmentCatalogItemRead]


class EquipmentInventoryUpdate(BaseModel):
    in_inventory: bool
    quantity: int = Field(default=1, ge=1, le=9999)
