from __future__ import annotations

from .catalog_seed_v1 import CATEGORY_META as EQUIPMENT_CATEGORY_META

CATEGORY_META = {
    **EQUIPMENT_CATEGORY_META,
    "engine-oil": ("Engine oil", "oil"),
    "coolant-antifreeze": ("Coolant & antifreeze", "coolant"),
    "washer-fluid": ("Windshield washer fluid", "washer-fluid"),
    "wheel-hardware": ("Wheel hardware", "lug"),
}
